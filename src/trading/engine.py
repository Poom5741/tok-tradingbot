"""Cast-based trading engine for executing real swaps on Pancake v2.

This module shells out to Foundry `cast` for on-chain interaction to:
- Query reserves and balances
- Approve tokens
- Execute swaps with slippage protection
- Monitor transaction confirmations

Security notes:
- Private key is read from environment `BOT_PK` and passed to `cast send`.
- Rate limiting prevents excessive trading bursts.
- Slippage calculation uses AMM constant product with configurable pool fee.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from typing import Optional, Sequence

from common import Settings


def _env(key: str, default: Optional[str] = None) -> Optional[str]:
    val = os.environ.get(key)
    return val if val is not None else default


def _run(cmd: Sequence[str], timeout: int = 60) -> tuple[int, str, str]:
    """Run a command and capture (returncode, stdout, stderr)."""
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


@dataclass
class TradeResult:
    tx_hash: Optional[str]
    ok: bool
    error: Optional[str] = None


class CastClient:
    def __init__(self, rpc_url: str, chain_id: int, private_key: str, legacy_tx: bool = True) -> None:
        self.rpc_url = rpc_url
        self.chain_id = chain_id
        self.private_key = private_key
        self.legacy_tx = legacy_tx

    def call(self, to: str, sig: str) -> tuple[int, str, str]:
        # e.g., cast call <address> "getReserves()" --rpc-url $RPC_URL
        cmd = [
            "cast",
            "call",
            to,
            sig,
            "--rpc-url",
            self.rpc_url,
        ]
        return _run(cmd)

    def send(self, to: str, sig: str, args: Sequence[str] | None = None, value_wei: int = 0,
             gas_price_gwei: Optional[float] = None, gas_limit: Optional[int] = None) -> TradeResult:
        # e.g., cast send --private-key $BOT_PK <to> "swapExactTokensForTokens(uint256,uint256,address[],address,uint256)" <args...>
        cmd = [
            "cast",
            "send",
            "--private-key",
            self.private_key,
            to,
            sig,
        ]
        for a in (args or []):
            cmd.append(a)
        cmd += ["--rpc-url", self.rpc_url]
        if self.legacy_tx:
            cmd.append("--legacy")
        if gas_price_gwei is not None:
            cmd += ["--gas-price", str(gas_price_gwei)]
        if gas_limit is not None:
            cmd += ["--gas-limit", str(gas_limit)]
        if value_wei > 0:
            cmd += ["--value", str(value_wei)]
        code, out, err = _run(cmd)
        if code != 0:
            return TradeResult(tx_hash=None, ok=False, error=err or out)
        # cast send prints tx hash on success, often last line
        tx_hash = None
        for line in out.splitlines()[::-1]:
            line = line.strip()
            if line.startswith("0x") and len(line) > 2:
                tx_hash = line
                break
        return TradeResult(tx_hash=tx_hash, ok=True, error=None)

    def receipt(self, tx_hash: str) -> tuple[int, str, str]:
        cmd = ["cast", "receipt", tx_hash, "--rpc-url", self.rpc_url]
        return _run(cmd)


def calc_amount_out(amount_in: int, reserve_in: int, reserve_out: int, fee_bps: int = 25) -> int:
    """Uniswap V2/Pancake V2 style amountOut with fee in basis points (default 25 = 0.25%)."""
    amount_in_with_fee = amount_in * (10000 - fee_bps)
    numerator = amount_in_with_fee * reserve_out
    denominator = reserve_in * 10000 + amount_in_with_fee
    return numerator // denominator


class TradingEngine:
    def __init__(
        self,
        settings: Settings,
        token0: str,
        token1: str,
        pair_address: str,
        router_address: str,
        client: CastClient,
    ) -> None:
        self.settings = settings
        self.token0 = token0
        self.token1 = token1
        self.pair = pair_address
        self.router = router_address
        self.client = client
        self.pool_fee_bps = int(_env("POOL_FEE_BPS", "25"))
        self.slippage_bps = int(_env("SLIPPAGE_BPS", "50"))
        self.min_trade_interval_s = int(_env("MIN_TRADE_INTERVAL_S", "30"))
        self.gas_price_gwei = float(_env("GAS_PRICE_GWEI", "1"))
        self.min_native_balance_wei = int(_env("MIN_NATIVE_BALANCE_WEI", "10000000000000000"))  # 0.01 in 18 decimals
        self.topup_amount_wei = int(_env("GAS_TOPUP_WEI", "0"))  # disabled by default
        self.topup_source_pk = _env("TOPUP_SOURCE_PK", "")
        self.topup_source_address = _env("TOPUP_SOURCE_ADDRESS", "")
        self.last_trade_ts: float = 0.0

    def _throttle(self) -> bool:
        now = time.time()
        return (now - self.last_trade_ts) < self.min_trade_interval_s

    def _require_allowance(self, token: str, owner: str, spender: str, amount: int) -> Optional[TradeResult]:
        # Simple approve; cast send token "approve(address,uint256)" spender amount
        # Owner derived from private key; ERC20 approvals do not require specifying owner here.
        return self.client.send(
            to=token,
            sig="approve(address,uint256)",
            args=[spender, str(amount)],
            gas_price_gwei=self.gas_price_gwei,
        )

    def get_reserves(self) -> tuple[int, int]:
        code, out, err = self.client.call(self.pair, "getReserves()")
        if code != 0:
            raise RuntimeError(f"getReserves failed: {err or out}")
        # cast returns e.g. "(uint112,uint112,uint32): (123,456,789)" or raw numbers
        # Extract two integers in the string
        nums = [int(x) for x in out.replace(",", " ").split() if x.isdigit()]
        if len(nums) < 2:
            raise RuntimeError(f"Unexpected getReserves output: {out}")
        return nums[0], nums[1]

    def native_balance(self, address: str) -> int:
        code, out, err = _run(["cast", "balance", address, "--rpc-url", self.client.rpc_url])
        if code != 0:
            raise RuntimeError(f"balance query failed: {err or out}")
        # cast balance prints integer wei
        try:
            return int(out.strip())
        except Exception:
            raise RuntimeError(f"Unexpected balance output: {out}")

    def ensure_gas(self, recipient: str) -> bool:
        """Ensure recipient has minimum native balance; optionally top up if configured."""
        try:
            bal = self.native_balance(recipient)
        except Exception:
            return False
        if bal >= self.min_native_balance_wei:
            return True
        # Try top-up if configured
        if self.topup_amount_wei > 0 and self.topup_source_pk and recipient:
            cmd = [
                "cast",
                "send",
                "--private-key",
                self.topup_source_pk,
                recipient,
                "--value",
                str(self.topup_amount_wei),
                "--rpc-url",
                self.client.rpc_url,
            ]
            if self.client.legacy_tx:
                cmd.append("--legacy")
            code, out, err = _run(cmd)
            if code != 0:
                return False
            # wait briefly to reflect new balance
            time.sleep(5.0)
            try:
                bal2 = self.native_balance(recipient)
                return bal2 >= self.min_native_balance_wei
            except Exception:
                return False
        return False

    def _min_out_with_slippage(self, amount_in: int, reserve_in: int, reserve_out: int) -> int:
        expected = calc_amount_out(amount_in, reserve_in, reserve_out, fee_bps=self.pool_fee_bps)
        return expected * (10000 - self.slippage_bps) // 10000

    def buy_token1(self, amount_token0_in: int, recipient: str) -> TradeResult:
        if self._throttle():
            return TradeResult(tx_hash=None, ok=False, error="rate_limited")
        if not self.ensure_gas(recipient):
            return TradeResult(tx_hash=None, ok=False, error="insufficient_gas_balance")
        r0, r1 = self.get_reserves()
        min_out = self._min_out_with_slippage(amount_token0_in, r0, r1)
        deadline = str(int(time.time()) + 60)
        path = [self.token0, self.token1]
        # Approve token0 if needed (optimistic approve for amount_in)
        self._require_allowance(self.token0, owner="", spender=self.router, amount=amount_token0_in)
        res = self.client.send(
            to=self.router,
            sig="swapExactTokensForTokens(uint256,uint256,address[],address,uint256)",
            args=[str(amount_token0_in), str(min_out), str(path), recipient, deadline],
            gas_price_gwei=self.gas_price_gwei,
        )
        if res.ok:
            self.last_trade_ts = time.time()
        return res

    def sell_token1(self, amount_token1_in: int, recipient: str) -> TradeResult:
        if self._throttle():
            return TradeResult(tx_hash=None, ok=False, error="rate_limited")
        if not self.ensure_gas(recipient):
            return TradeResult(tx_hash=None, ok=False, error="insufficient_gas_balance")
        r0, r1 = self.get_reserves()
        min_out = self._min_out_with_slippage(amount_token1_in, r1, r0)
        deadline = str(int(time.time()) + 60)
        path = [self.token1, self.token0]
        self._require_allowance(self.token1, owner="", spender=self.router, amount=amount_token1_in)
        res = self.client.send(
            to=self.router,
            sig="swapExactTokensForTokens(uint256,uint256,address[],address,uint256)",
            args=[str(amount_token1_in), str(min_out), str(path), recipient, deadline],
            gas_price_gwei=self.gas_price_gwei,
        )
        if res.ok:
            self.last_trade_ts = time.time()
        return res

    def wait_confirmations(self, tx_hash: str, confirmations: int = 1, timeout_s: int = 120) -> bool:
        start = time.time()
        while time.time() - start < timeout_s:
            code, out, err = self.client.receipt(tx_hash)
            if code == 0 and out:
                # naive: if receipt returned, consider confirmed. Further parsing can check status=1
                return True
            time.sleep(2.0)
        return False