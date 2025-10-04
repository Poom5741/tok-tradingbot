"""Command-line interface for the microstructure bot (paper trading)."""

from __future__ import annotations

import argparse
from typing import Sequence, Optional
import requests

from common import GitHubClient, GitHubError, Settings, configure_logging
from .orchestrator import MicrostructureBot


def create_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(description="tokBot microstructure bot controller")
    parser.add_argument(
        "--env-file",
        action="append",
        default=None,
        help="Path to a .env file to read before executing commands. Can be provided multiple times.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    paper_parser = subparsers.add_parser("paper", help="Run paper-trading loop")
    paper_parser.add_argument(
        "--loops",
        type=int,
        default=1,
        help="Number of paper-trading iterations to run",
    )
    paper_parser.add_argument("--token0", help="ERC20 address for token0 (checksummed)")
    paper_parser.add_argument("--token1", help="ERC20 address for token1 (checksummed)")
    paper_parser.add_argument(
        "--dex",
        choices=["uniswap-v2", "uniswap-v3"],
        default="uniswap-v2",
        help="DEX used to resolve the pair/pool",
    )
    paper_parser.add_argument("--chain-id", type=int, default=1, help="Chain ID for resolution (default: 1)")
    paper_parser.add_argument(
        "--fee-bps",
        type=int,
        default=None,
        help="Fee tier (bps) for Uniswap v3 pools (e.g., 500/3000/10000)",
    )
    paper_parser.set_defaults(handler=_handle_paper)

    issue_parser = subparsers.add_parser(
        "issue",
        help="Interact with GitHub issues for bot notes",
    )
    issue_subparsers = issue_parser.add_subparsers(dest="issue_command", required=True)

    issue_read = issue_subparsers.add_parser(
        "read",
        help="Read an issue and recent comments",
    )
    issue_read.add_argument("--issue", type=int, required=True, help="Issue number to read")
    issue_read.add_argument("--repo", help="Repository override in owner/repo form")
    issue_read.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of most recent comments to display (default: 5)",
    )
    issue_read.set_defaults(handler=_handle_issue_read)

    issue_comment = issue_subparsers.add_parser(
        "comment",
        help="Append a comment to an issue",
    )
    issue_comment.add_argument("--issue", type=int, required=True, help="Issue number to comment on")
    issue_comment.add_argument("--repo", help="Repository override in owner/repo form")
    issue_comment.add_argument(
        "--body",
        required=True,
        help="Comment body to append. Use quotes for multi-line text.",
    )
    issue_comment.set_defaults(handler=_handle_issue_comment)

    return parser


def run_cli(argv: Sequence[str] | None = None) -> int:
    """Entry point for handling CLI execution."""
    parser = create_parser()
    args = parser.parse_args(argv)

    configure_logging()
    settings = Settings.from_env(env_files=args.env_file)
    bot = MicrostructureBot(settings)

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.error("No handler configured for the provided command")
    return handler(args, bot)


def _handle_paper(args: argparse.Namespace, bot: MicrostructureBot) -> int:
    """Run the microstructure bot in paper mode and print outcomes."""
    # If token addresses are provided, attempt to resolve the DEX pair/pool
    if getattr(args, "token0", None) and getattr(args, "token1", None):
        pair_addr = _resolve_pair_address(
            token0=args.token0,
            token1=args.token1,
            dex=getattr(args, "dex", "uniswap-v2"),
            chain_id=getattr(args, "chain_id", 1),
            fee_bps=getattr(args, "fee_bps", None),
        )
        if pair_addr:
            print(f"Resolved Pair ({getattr(args, 'dex', 'uniswap-v2')}, chain {getattr(args, 'chain_id', 1)}): {pair_addr}")
        else:
            print("Warning: Could not resolve pair/pool for provided tokens.")

    outcomes = bot.run_paper(loops=args.loops)
    print("Paper Trading Outcomes:")
    for i, out in enumerate(outcomes, start=1):
        line = [f"[{i}] State: {out.state}"]
        if out.signal is not None:
            s = out.signal
            line.append(
                f"FT={s.ft:.2f} IP={s.ip_bps:.1f} SE={s.se:.2f} OFI={s.ofi:.2f} LD={s.ld:.2f} DEV={s.dev_bps:.1f}"
            )
        if out.position is not None:
            line.append(f"Pos size={out.position.size:.2f} entry={out.position.entry_price:.2f}")
        if out.exited:
            line.append("Exited")
        print(" | ".join(line))
    return 0


def _resolve_pair_address(
    token0: str,
    token1: str,
    dex: str = "uniswap-v2",
    chain_id: int = 1,
    fee_bps: Optional[int] = None,
) -> Optional[str]:
    """Resolve a DEX pair/pool address for two tokens using The Graph.

    Supports:
    - Uniswap V2 (pairs)
    - Uniswap V3 (pools) with optional fee tier
    """
    t0 = token0.lower()
    t1 = token1.lower()
    if chain_id != 1:
        # Only Ethereum mainnet supported by default here
        return None
    if dex == "uniswap-v2":
        url = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v2"
        q_exact = "query($a:String!,$b:String!){pairs(where:{token0:$a, token1:$b}){ id token0{ id } token1{ id } }}"
        q_reverse = "query($a:String!,$b:String!){pairs(where:{token0:$b, token1:$a}){ id token0{ id } token1{ id } }}"
        for q in (q_exact, q_reverse):
            resp = requests.post(url, json={"query": q, "variables": {"a": t0, "b": t1}}, timeout=10)
            if resp.ok:
                data = resp.json().get("data", {}).get("pairs", [])
                if data:
                    return data[0]["id"]
    elif dex == "uniswap-v3":
        url = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"
        # Filter by fee tier if provided
        if fee_bps is not None:
            q_exact = (
                "query($a:String!,$b:String!,$fee:Int!){pools(where:{token0:$a, token1:$b, feeTier:$fee})"
                "{ id token0{ id } token1{ id } feeTier }}"
            )
            q_reverse = (
                "query($a:String!,$b:String!,$fee:Int!){pools(where:{token0:$b, token1:$a, feeTier:$fee})"
                "{ id token0{ id } token1{ id } feeTier }}"
            )
            vars = {"a": t0, "b": t1, "fee": int(fee_bps)}
        else:
            q_exact = (
                "query($a:String!,$b:String!){pools(where:{token0:$a, token1:$b})"
                "{ id token0{ id } token1{ id } feeTier }}"
            )
            q_reverse = (
                "query($a:String!,$b:String!){pools(where:{token0:$b, token1:$a})"
                "{ id token0{ id } token1{ id } feeTier }}"
            )
            vars = {"a": t0, "b": t1}
        for q in (q_exact, q_reverse):
            resp = requests.post(url, json={"query": q, "variables": vars}, timeout=10)
            if resp.ok:
                data = resp.json().get("data", {}).get("pools", [])
                if data:
                    # If multiple, prefer lowest fee
                    data.sort(key=lambda p: int(p.get("feeTier", 99999)))
                    return data[0]["id"]
    return None


def _build_github_client(args_repo: str | None, settings: Settings) -> GitHubClient:
    repo = args_repo or settings.github_repo
    return GitHubClient(repo=repo)


def _handle_issue_read(args: argparse.Namespace, bot: MicrostructureBot) -> int:
    client = _build_github_client(args.repo, bot.settings)
    try:
        issue_data = client.read_issue(args.issue)
    except GitHubError as exc:  # pragma: no cover - CLI error path
        print(f"GitHub error: {exc}")
        return 1

    title = issue_data.get("title", "(no title)")
    body = issue_data.get("body", "")
    print(f"Issue #{issue_data.get('number', args.issue)} | {title}")
    if body:
        print("-" * 40)
        print(body.strip())
    comments: list[dict] = issue_data.get("comments_data", [])
    if comments:
        print("-" * 40)
        for comment in comments[: args.limit]:
            author = comment.get("user", {}).get("login", "unknown")
            print(f"@{author}: {comment.get('body', '').strip()}")
    else:
        print("(No comments found)")
    return 0


def _handle_issue_comment(args: argparse.Namespace, bot: MicrostructureBot) -> int:
    client = _build_github_client(args.repo, bot.settings)
    try:
        client.create_comment(args.issue, args.body)
    except GitHubError as exc:  # pragma: no cover - CLI error path
        print(f"GitHub error: {exc}")
        return 1
    print(f"Comment posted to issue #{args.issue}.")
    return 0
