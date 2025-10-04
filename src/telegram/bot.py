"""Minimal Telegram bot service for tokBot.

Provides simple chat commands to drive paper trading and pair resolution
without additional dependencies beyond `requests` and `python-dotenv`.
"""

from __future__ import annotations

import os
import time
from typing import Optional, Iterable

import requests
from dotenv import dotenv_values

from common import Settings
from tokbot.orchestrator import MicrostructureBot
from tokbot.integrations.uniswap import resolve_pair_address


def _load_overrides(env_files: Iterable[str] | None) -> dict[str, str]:
    values: dict[str, str] = {}
    if env_files:
        for candidate in env_files:
            try:
                if os.path.isfile(candidate):
                    file_vals = {
                        k: v for k, v in dotenv_values(candidate).items() if v is not None
                    }
                    values.update(file_vals)
            except Exception:
                # Best-effort .env loading; ignore malformed files
                pass
    return values


def _lookup(key: str, overrides: dict[str, str]) -> Optional[str]:
    return os.environ.get(key) or overrides.get(key)


class TelegramBot:
    """Long-polling Telegram bot for tokBot.

    Commands:
    - /start, /help: Show help
    - /status: Show bot status
    - /paper [loops]: Run paper-trading for N loops (default: 1)
    - /pair <token0> <token1> <dex> [fee_bps]: Resolve pair/pool address via Uniswap subgraphs
    """

    def __init__(self, settings: Settings, env_files: Iterable[str] | None = None):
        self.settings = settings
        self.overrides = _load_overrides(env_files)

        token = _lookup("TELEGRAM_BOT_TOKEN", self.overrides)
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is required in environment or .env")
        self.token = token
        admin = _lookup("TELEGRAM_ADMIN_ID", self.overrides)
        self.admin_id: Optional[int] = int(admin) if admin else None

        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.offset: Optional[int] = None

        # Microstructure bot instance used for /paper
        self.bot = MicrostructureBot(settings)

    def _send(self, chat_id: int, text: str) -> None:
        try:
            requests.post(
                f"{self.base_url}/sendMessage",
                json={"chat_id": chat_id, "text": text},
                timeout=10,
            )
        except Exception:
            # Ignore transient network errors; polling loop continues
            pass

    def _authorized(self, message: dict) -> bool:
        if self.admin_id is None:
            return True
        sender = message.get("from", {})
        return int(sender.get("id", 0)) == self.admin_id

    def _handle(self, message: dict) -> None:
        chat = message.get("chat", {})
        chat_id = int(chat.get("id"))
        text = (message.get("text") or "").strip()
        if not text:
            return

        # Allow basic discovery commands without admin restriction
        if text.startswith("/whoami"):
            sender = message.get("from", {})
            user_id = int(sender.get("id", 0))
            chat_type = chat.get("type", "private")
            self._send(chat_id, f"chat_id={chat_id} type={chat_type} user_id={user_id}")
            return

        if text.startswith("/start") or text.startswith("/help"):
            self._send(
                chat_id,
                "Commands:\n"
                "/whoami\n"
                "/paper [loops]\n"
                "/pair <token0> <token1> <dex> [fee_bps]\n"
                "/status",
            )
            return

        # Enforce admin restriction for stateful commands
        if not self._authorized(message):
            self._send(chat_id, "Unauthorized. Set TELEGRAM_ADMIN_ID to allow your user.")
            return

        if text.startswith("/status"):
            self._send(chat_id, f"tokBot ready. env={self.settings.environment}")
            return

        if text.startswith("/whoami"):
            sender = message.get("from", {})
            user_id = int(sender.get("id", 0))
            chat_type = chat.get("type", "private")
            self._send(chat_id, f"chat_id={chat_id} type={chat_type} user_id={user_id}")
            return

        if text.startswith("/pair"):
            parts = text.split()
            if len(parts) < 4:
                self._send(chat_id, "Usage: /pair <token0> <token1> <dex> [fee_bps]")
                return
            token0, token1, dex = parts[1], parts[2], parts[3]
            fee_bps = int(parts[4]) if len(parts) > 4 else None
            addr = resolve_pair_address(
                token0=token0,
                token1=token1,
                dex=dex,
                chain_id=1,
                fee_bps=fee_bps,
            )
            if addr:
                self._send(chat_id, f"{dex} pair/pool: {addr}")
            else:
                self._send(chat_id, "Pair/pool not found.")
            return

        if text.startswith("/paper"):
            parts = text.split()
            loops = 1
            if len(parts) > 1:
                try:
                    loops = max(1, int(parts[1]))
                except ValueError:
                    pass
            outcomes = self.bot.run_paper(loops=loops)
            lines: list[str] = []
            for i, out in enumerate(outcomes, start=1):
                segs = [f"[{i}] {out.state}"]
                if out.signal is not None:
                    s = out.signal
                    segs.append(
                        f"FT={s.ft:.2f} IP={s.ip_bps:.1f} SE={s.se:.2f} OFI={s.ofi:.2f} LD={s.ld:.2f} DEV={s.dev_bps:.1f}"
                    )
                if out.position is not None:
                    segs.append(f"pos={out.position.size:.2f} entry={out.position.entry_price:.2f}")
                if out.exited:
                    segs.append("Exited")
                lines.append(" | ".join(segs))
            summary = "Paper Trading Outcomes:\n" + "\n".join(lines[:25])
            self._send(chat_id, summary)
            return

        self._send(chat_id, "Unknown command. Use /help.")

    def run(self, poll_interval: float = 1.0) -> None:
        """Run the long-polling loop. Blocks indefinitely."""
        while True:
            params: dict[str, int] = {"timeout": 30}
            if self.offset is not None:
                params["offset"] = self.offset
            try:
                resp = requests.get(f"{self.base_url}/getUpdates", params=params, timeout=35)
                if resp.ok:
                    updates = resp.json().get("result", [])
                    for update in updates:
                        self.offset = max(self.offset or 0, int(update.get("update_id", 0)) + 1)
                        message = update.get("message") or update.get("channel_post")
                        if message:
                            self._handle(message)
                else:
                    time.sleep(poll_interval)
            except Exception:
                time.sleep(poll_interval)