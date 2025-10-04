"""Live mode controller (dry-run stub).

This module scaffolds a live trading mode while keeping strict safeguards:
- Reads RPC/chain/account details from environment (via .env if provided)
- Uses MicrostructureBot for decisioning but performs NO on-chain execution
- Prints intended actions so wiring can be validated before real trading

To enable real trading later, integrate Web3 and DEX routers here with
explicit opt-in flags and risk guard rails.
"""

from __future__ import annotations

import os
from typing import Optional, Iterable

from dotenv import dotenv_values

from common import Settings
from .orchestrator import MicrostructureBot, BotOutcome
from trading.engine import TradingEngine, CastClient


def _load_overrides(env_files: Iterable[str] | None) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for path in env_files or []:
        try:
            overrides.update({k: v for k, v in dotenv_values(path).items() if v is not None})
        except Exception:
            pass
    return overrides


def _lookup(key: str, overrides: dict[str, str]) -> Optional[str]:
    return os.environ.get(key) or overrides.get(key)


class LiveRunner:
    def __init__(self, settings: Settings, env_files: Iterable[str] | None = None) -> None:
        self.settings = settings
        self.overrides = _load_overrides(env_files)

        # Basic env wiring for future on-chain integration
        self.rpc_url = _lookup("RPC_URL", self.overrides)
        self.chain_id = int(_lookup("CHAIN_ID", self.overrides) or "1")
        self.bot_pk = _lookup("BOT_PK", self.overrides)
        self.router_address = _lookup("ROUTER_ADDRESS", self.overrides)
        self.token0 = _lookup("TOKEN0", self.overrides)
        self.token1 = _lookup("TOKEN1", self.overrides)
        self.pair_address = _lookup("PAIR_ADDRESS", self.overrides)
        self.use_cast = (_lookup("USE_CAST", self.overrides) or "1") == "1"
        self.live_enabled = (_lookup("TOKBOT_LIVE", self.overrides) or "0") == "1"

        self.bot = MicrostructureBot(settings)
        self.engine: TradingEngine | None = None
        if self.use_cast and self.live_enabled and self.rpc_url and self.bot_pk and self.router_address and self.token0 and self.token1 and self.pair_address:
            client = CastClient(rpc_url=self.rpc_url, chain_id=self.chain_id, private_key=self.bot_pk, legacy_tx=True)
            self.engine = TradingEngine(
                settings=settings,
                token0=self.token0,
                token1=self.token1,
                pair_address=self.pair_address,
                router_address=self.router_address,
                client=client,
            )

    def run_dry(self, *, loops: int = 1, pair_address: Optional[str] = None) -> list[BotOutcome]:
        """Run live flow in dry-run mode: no transactions, only prints and records outcomes."""
        outcomes = self.bot.run_paper(loops=loops)
        # In a real implementation, we would use pair_address and RPC here.
        return outcomes

    def run_once_live(self) -> Optional[str]:
        """Execute a single live decision using TradingEngine if enabled.

        Returns a tx hash on trade, or None if no trade.
        """
        if not self.engine:
            return None
        # Simple directional decision: buy token1 when ft>0, sell when ft<0
        outs = self.bot.run_paper(loops=1)
        if not outs:
            return None
        out = outs[-1]
        sig = out.signal
        if sig is None:
            return None
        recipient = _lookup("BOT_ADDRESS", self.overrides) or ""
        # Default trade size in smallest units (e.g., wei). For demo, 1e16 (~0.01 in 18 decimals)
        trade_size = int(float(_lookup("TRADE_SIZE_WEI", self.overrides) or "10000000000000000"))
        try:
            if sig.ft >= 0:
                res = self.engine.buy_token1(amount_token0_in=trade_size, recipient=recipient)
            else:
                res = self.engine.sell_token1(amount_token1_in=trade_size, recipient=recipient)
            if not res.ok:
                print(f"Trade failed: {res.error}")
                return None
            txh = res.tx_hash or ""
            # Wait for 1 confirmation
            confirmed = self.engine.wait_confirmations(txh, confirmations=1, timeout_s=120)
            print(f"Trade tx={txh} confirmed={confirmed}")
            return txh
        except Exception as exc:
            print(f"Live trade error: {exc}")
            return None