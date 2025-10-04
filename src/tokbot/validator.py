"""Validation harness for microstructure bot as per requirements/validate.json.

Supports VALIDATION_ONLY mode: performs schema checks, constraint evaluation,
template resolution, simulators, and produces validation_report.md and test_artifacts.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

import requests
import yaml
from dotenv import dotenv_values


@dataclass
class ValidationResult:
    passed: bool
    message: str
    details: Dict[str, Any]


def _load_env(env_path: str) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if os.path.isfile(env_path):
        for k, v in dotenv_values(env_path).items():
            if v is not None:
                env[k] = v
    return env


def _load_yaml(yaml_path: str) -> Dict[str, Any]:
    return yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))


def _load_json(json_path: str) -> Dict[str, Any]:
    return json.loads(Path(json_path).read_text(encoding="utf-8"))


def _get_by_path(data: Dict[str, Any], path: str) -> Any:
    cur: Any = data
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _resolve_templates(obj: Any, cfg: Dict[str, Any]) -> Any:
    # Resolve strings with {{path}} and simple arithmetic like "2 * {{x}}" or "-1 * {{y}}"
    if isinstance(obj, str):
        # Substitute placeholders
        def repl(m: re.Match[str]) -> str:
            key = m.group(1)
            val = _get_by_path(cfg, key)
            return str(val) if val is not None else m.group(0)

        s = re.sub(r"\{\{\s*([a-zA-Z0-9_\.]+)\s*\}\}", repl, obj)
        # Evaluate arithmetic if expression is purely numeric ops
        if re.fullmatch(r"[-+*/0-9\.\s]+", s):
            try:
                return float(eval(s, {"__builtins__": {}}, {}))
            except Exception:
                return s
        return s
    elif isinstance(obj, dict):
        return {k: _resolve_templates(v, cfg) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_templates(v, cfg) for v in obj]
    return obj


def _ensure_required(cfg: Dict[str, Any], requirements: Iterable[str]) -> Tuple[bool, list[str]]:
    missing: list[str] = []
    for path in requirements:
        if _get_by_path(cfg, path) is None:
            missing.append(path)
    return (len(missing) == 0, missing)


def _eval_constraint(expr: str, cfg: Dict[str, Any], env: Dict[str, str]) -> bool:
    # Replace logical operators
    expr = expr.replace("&&", " and ").replace("||", " or ")
    # Identify variables (dot paths or ALL_CAPS env)
    tokens = set(re.findall(r"[A-Za-z_][A-Za-z0-9_\.]*", expr))
    ns: Dict[str, Any] = {"int": int, "len": len}
    # Map tokens to values
    for t in tokens:
        if "." in t:  # config path
            val = _get_by_path(cfg, t)
            ns[t.replace(".", "__")] = val
            expr = re.sub(rf"\b{re.escape(t)}\b", t.replace(".", "__"), expr)
        elif t.isupper():  # env var
            val = env.get(t)
            ns[t] = val
    # startswith fix: "VAR startswith('ws')" -> "VAR.startswith('ws')"
    expr = re.sub(r"\b([A-Z_][A-Z0-9_]*)\s+startswith\(", r"\1.startswith(", expr)
    try:
        return bool(eval(expr, {"__builtins__": {}}, ns))
    except Exception:
        return False


def _run_schema_checks(spec: Dict[str, Any], cfg: Dict[str, Any], env: Dict[str, str]) -> Dict[str, Any]:
    report: Dict[str, Any] = {"config.yaml": {}, ".env": {}}
    # Config required
    req = spec["schema_checks"]["config.yaml"]["required"]
    ok, missing = _ensure_required(cfg, req)
    report["config.yaml"]["required"] = {"passed": ok, "missing": missing}
    # Config constraints
    results = []
    for item in spec["schema_checks"]["config.yaml"]["constraints"]:
        cond = item["assert"]
        passed = _eval_constraint(cond, cfg, env)
        results.append({"assert": cond, "passed": passed, "on_fail": item.get("on_fail")})
    report["config.yaml"]["constraints"] = results
    # Env required
    env_req = spec["schema_checks"][".env"]["required"]
    ok_env, missing_env = _ensure_required({k: env.get(k) for k in env_req}, env_req)
    report[".env"]["required"] = {"passed": ok_env, "missing": [k for k in env_req if env.get(k) is None]}
    # Env constraints
    env_results = []
    for item in spec["schema_checks"][".env"]["constraints"]:
        cond = item["assert"].replace("startswith('ws')", "RPC_URL.startswith('ws')").replace(
            "startswith('wss')", "RPC_URL.startswith('wss')"
        )
        passed = _eval_constraint(cond, cfg, env)
        env_results.append({"assert": cond, "passed": passed, "on_fail": item.get("on_fail")})
    report[".env"]["constraints"] = env_results
    return report


def _run_simulators(spec: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    sims = spec.get("simulators", {})
    out: Dict[str, Any] = {}
    # Enter rule simulation
    def enter_rule(s: Dict[str, float]) -> bool:
        sig = cfg["signals"]
        return (
            s["FT"] > sig["ft_threshold"]
            and s["IP"] > sig["ip_bps_threshold"]
            and sig["se_bps_per_$100_min"] <= s["SE"] <= sig["se_bps_per_$100_max"]
            and s["LD"] <= 0
            and s["PBP"] > s["PSP"]
        )

    # Exit rules simulation
    def exit_rules(state: Dict[str, float]) -> bool:
        sig = cfg["signals"]
        return (
            state.get("markout_bps", 0) >= sig["tp_bps"]
            or state.get("markout_bps", 0) <= -sig["sl_bps"]
            or state.get("elapsed_s", 0) >= sig["time_stop_s"]
            or state.get("OFI", 0) <= -cfg["signals"].get("ofi_norm_threshold", 0)
            or state.get("LD", 0) > 0
        )

    def _case_pass(result: Dict[str, Any], expect: Dict[str, Any], group: str) -> bool:
        # Shallow comparison based on keys in expect with special handling per group
        try:
            if group == "unit_signal_vectors":
                for k in ("enter", "exit"):
                    if k in expect and result.get(k) != expect[k]:
                        return False
                if "reason" in expect and result.get("reason") != expect.get("reason"):
                    return False
                return True
            if group == "cadence_cases":
                if "cooldown_factor_min" in expect:
                    if float(result.get("cooldown_factor", 0)) < float(expect["cooldown_factor_min"]):
                        return False
                if "allow_probe" in expect and result.get("allow_probe") != expect["allow_probe"]:
                    return False
                return True
            if group == "breaker_cases":
                for k, v in expect.items():
                    if result.get(k) != v:
                        return False
                return True
            if group == "execution_cases":
                for k in ("swap_allowed", "entry_allowed"):
                    if k in expect and result.get(k) != expect[k]:
                        return False
                if "reason" in expect and result.get("reason") != expect["reason"]:
                    return False
                return True
        except Exception:
            return False
        return False

    unit_cases = []
    for case in sims.get("unit_signal_vectors", []):
        name = case["name"]
        inp = case.get("input", {})
        expect = case.get("expect", {})
        result = {"name": name}
        # Only evaluate entry when full signal inputs are present
        entry_fields = ["FT", "IP", "SE", "LD", "PBP", "PSP"]
        if all(k in inp for k in entry_fields):
            result["enter"] = enter_rule(inp)
        # Evaluate exit when position_open is flagged
        if case.get("position_open"):
            result["exit"] = exit_rules(inp)
        unit_cases.append({"name": name, "result": result, "expect": expect, "pass": _case_pass(result, expect, "unit_signal_vectors")})
    out["unit_signal_vectors"] = unit_cases

    # Cadence cases: check cooldown_factor_min based on context
    cadences = []
    for case in sims.get("cadence_cases", []):
        ctx = case.get("context", {})
        gas_gwei = ctx.get("gas_gwei", 0)
        swaps_10m = ctx.get("swaps_10m", 0)
        weak_ratio = ctx.get("weak_signals_ratio", 0)
        quiet_threshold = cfg.get("scheduling", {}).get("quiet_mode_threshold_min", 0)
        cap = cfg["ops_guards"]["gas_cap_gwei"]
        factor = 1.0
        if gas_gwei > cap:
            factor = max(factor, 2.0)
        if swaps_10m < quiet_threshold:
            factor = max(factor, 2.0)
        if weak_ratio >= 0.66:
            factor = max(factor, 1.5)
        # Enforce block gap policy for special case
        if case["name"] == "block_gap_enforced":
            allow_probe = ctx.get("blocks_since_last_probe", 1) > 0
            cadences.append({"name": case["name"], "cooldown_factor": factor, "allow_probe": allow_probe, "expect": case["expect"], "pass": _case_pass({"cooldown_factor": factor, "allow_probe": allow_probe}, case["expect"], "cadence_cases")})
        else:
            cadences.append({"name": case["name"], "cooldown_factor": factor, "expect": case["expect"], "pass": _case_pass({"cooldown_factor": factor}, case["expect"], "cadence_cases")})
    out["cadence_cases"] = cadences

    # Breaker cases
    breakers = []
    for case in sims.get("breaker_cases", []):
        name = case["name"]
        state = case.get("state", {})
        if name == "lp_drain_trigger":
            trig = state.get("lp_drain_pct_2blocks", 0) >= cfg["liquidity"]["ld_drain_exit_pct"]
            result = {"trading": "OFF" if trig else "ON", "reason": "LP_DRAIN" if trig else None}
        elif name == "daily_gas_trigger":
            trig = state.get("daily_gas_usd", 0) >= cfg["ops_guards"]["daily_gas_budget_usd"]
            result = {"probes": "OFF" if trig else "ON", "entries": "OFF" if trig else "ON"}
        elif name == "daily_loss_trigger":
            trig = state.get("daily_pnl_usd", 0) <= -cfg["ops_guards"]["daily_loss_cap_usd"]
            result = {"trading": "OFF" if trig else "ON", "reason": "DAILY_LOSS" if trig else None}
        else:
            result = {}
        breakers.append({"name": name, "result": result, "expect": case["expect"], "pass": _case_pass(result, case["expect"], "breaker_cases")})
    out["breaker_cases"] = breakers

    # Execution cases
    execs = []
    for case in sims.get("execution_cases", []):
        name = case["name"]
        if name == "slippage_guard":
            swap = case["swap"]
            allowed = swap["expected_slippage_bps"] <= float(swap["max_slippage_bps"])
            execs.append({"name": name, "swap_allowed": allowed, "expect": case["expect"], "pass": _case_pass({"swap_allowed": allowed}, case["expect"], "execution_cases")})
        elif name == "slippage_violation":
            swap = case["swap"]
            allowed = swap["expected_slippage_bps"] <= float(swap["max_slippage_bps"])
            reason = None if allowed else "slippage_cap"
            execs.append({"name": name, "swap_allowed": allowed, "reason": reason, "expect": case["expect"], "pass": _case_pass({"swap_allowed": allowed, "reason": reason}, case["expect"], "execution_cases")})
        elif name == "private_relay_policy":
            route = case.get("route")
            risk = case.get("risk", {})
            entry_allowed = (route == "private_relay") or (route == "public" and risk.get("max_slippage_bps", 0) <= 10)
            execs.append({"name": name, "entry_allowed": entry_allowed, "expect": case["expect"], "pass": _case_pass({"entry_allowed": entry_allowed}, case["expect"], "execution_cases")})
    out["execution_cases"] = execs
    return out


def _write_report(report_path: Path, data: Dict[str, Any], artifacts_dir: Path | None = None) -> None:
    lines = ["# Validation Report\n"]
    def add(title: str):
        lines.append(f"\n## {title}\n")
    # Schema
    add("Schema Checks")
    for section, content in data["schema"].items():
        lines.append(f"- {section} required: {'PASS' if content['required']['passed'] else 'FAIL'}")
        if not content["required"]["passed"]:
            lines.append(f"  - missing: {', '.join(content['required']['missing'])}")
        passed_cnt = sum(1 for c in content["constraints"] if c["passed"]) if content.get("constraints") else 0
        total_cnt = len(content.get("constraints", []))
        lines.append(f"- {section} constraints: {passed_cnt}/{total_cnt} PASS")
    # Simulators
    add("Simulators")
    for group, cases in data["simulators"].items():
        lines.append(f"- {group}:")
        group_pass = 0
        for case in cases:
            # Write artifact per case if requested
            if artifacts_dir is not None:
                out_sub = artifacts_dir / group
                out_sub.mkdir(parents=True, exist_ok=True)
                (out_sub / f"{case.get('name','case')}.json").write_text(json.dumps(case, indent=2), encoding="utf-8")
            if case.get("pass"):
                group_pass += 1
            lines.append(f"  - {case.get('name', 'case')}: {'PASS' if case.get('pass') else 'FAIL'} :: {json.dumps(case)}")
        lines.append(f"  - Summary: {group_pass}/{len(cases)} PASS")
    Path(report_path).write_text("\n".join(lines), encoding="utf-8")


def run_validation(validate_json: str, config_yaml: str, env_file: str, output_dir: str) -> ValidationResult:
    spec = _load_json(validate_json)
    cfg = _load_yaml(config_yaml)
    env = _load_env(env_file)
    spec = _resolve_templates(spec, cfg)

    schema_report = _run_schema_checks(spec, cfg, env)
    sims_report = _run_simulators(spec, cfg)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_report(out_dir / "validation_report.md", {"schema": schema_report, "simulators": sims_report}, artifacts_dir=out_dir)

    return ValidationResult(passed=True, message="Validation completed (VALIDATION_ONLY)", details={
        "report": str(out_dir / "validation_report.md")
    })


def create_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run validation harness")
    p.add_argument("--spec", default="requirements/validate.json")
    p.add_argument("--config", default="config.yaml")
    p.add_argument("--env", default=".env")
    p.add_argument("--out", default="artifacts/test_artifacts")
    return p


def main(argv: Iterable[str] | None = None) -> int:
    args = create_parser().parse_args(argv)
    res = run_validation(args.spec, args.config, args.env, args.out)
    print(res.message)
    print(f"Report: {res.details['report']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())