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

        self.bot = MicrostructureBot(settings)

    def run_dry(self, *, loops: int = 1, pair_address: Optional[str] = None) -> list[BotOutcome]:
        """Run live flow in dry-run mode: no transactions, only prints and records outcomes."""
        outcomes = self.bot.run_paper(loops=loops)
        # In a real implementation, we would use pair_address and RPC here.
        return outcomes