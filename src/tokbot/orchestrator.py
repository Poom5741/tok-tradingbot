"""Microstructure bot orchestration for paper trading."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import random
from typing import Optional

from common import Settings


class BotState(str, Enum):
    IDLE = "IDLE"
    PING = "PING"
    SCORE = "SCORE"
    ENTER = "ENTER"
    MANAGE = "MANAGE"
    EXIT = "EXIT"


@dataclass
class SignalSnapshot:
    ft: float  # Follow-Through ratio
    ip_bps: float  # Impact Persistence (bps)
    se: float  # Slippage Elasticity ($100)
    ofi: float  # Order-Flow Imbalance
    ld: float  # Liquidity Delta (negative is LP drain)
    dev_bps: float  # Spot–TWAP deviation (bps)
    pbp: float  # Pending buy pressure (gas-weighted)
    psp: float  # Pending sell pressure


@dataclass
class Position:
    size: float
    entry_price: float


@dataclass
class BotOutcome:
    state: BotState
    signal: Optional[SignalSnapshot] = None
    position: Optional[Position] = None
    exited: bool = False


class MicrostructureBot:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.state = BotState.IDLE
        self.position: Optional[Position] = None

    def ready(self) -> bool:
        return True

    def gas_ok(self) -> bool:
        return True

    def quiet_market(self) -> bool:
        return False

    def probe(self) -> SignalSnapshot:
        # Deterministic-ish stub based on environment for repeatability
        rnd = random.Random(self.settings.environment)
        return SignalSnapshot(
            ft=1.5 + rnd.random(),
            ip_bps=2 + rnd.random() * 10,
            se=0.2 + rnd.random() * 2,
            ofi=rnd.uniform(-1.0, 1.0),
            ld=rnd.uniform(-2.0, 2.0),
            dev_bps=rnd.uniform(-5.0, 5.0),
            pbp=rnd.random() * 2,
            psp=rnd.random() * 2,
        )

    def strong_reaction(self, s: SignalSnapshot) -> bool:
        return (
            s.ft >= self.settings.ft_min
            and s.ip_bps >= self.settings.ip_min_bps
            and s.ld <= 0
            and s.pbp > s.psp
            and self.settings.se_min <= s.se <= self.settings.se_max
        )

    def size_from(self, s: SignalSnapshot) -> float:
        # Simple proportional sizing
        return min(1.0, (s.ft - 1.0) * 0.5)

    def enter(self, size: float, price: float) -> Position:
        self.position = Position(size=size, entry_price=price)
        return self.position

    def exit_conditions(self, s: SignalSnapshot) -> bool:
        # Exit on OFI flip or LP add
        return s.ofi < 0 or s.ld > 0

    def exit(self) -> None:
        self.position = None

    def run_paper(self, *, loops: int = 1) -> list[BotOutcome]:
        outcomes: list[BotOutcome] = []
        for _ in range(loops):
            if not (self.ready() and self.gas_ok() and not self.quiet_market()):
                outcomes.append(BotOutcome(state=BotState.IDLE))
                continue

            self.state = BotState.PING
            sig = self.probe()
            outcomes.append(BotOutcome(state=BotState.PING, signal=sig))

            self.state = BotState.SCORE
            outcomes.append(BotOutcome(state=BotState.SCORE, signal=sig))

            if self.strong_reaction(sig):
                self.state = BotState.ENTER
                pos = self.enter(self.size_from(sig), price=100.0)
                outcomes.append(BotOutcome(state=BotState.ENTER, signal=sig, position=pos))

                self.state = BotState.MANAGE
                outcomes.append(BotOutcome(state=BotState.MANAGE, signal=sig, position=pos))

                if self.exit_conditions(sig):
                    self.state = BotState.EXIT
                    self.exit()
                    outcomes.append(BotOutcome(state=BotState.EXIT, signal=sig, exited=True))
            else:
                # No enter, remain idle
                outcomes.append(BotOutcome(state=BotState.IDLE, signal=sig))

        return outcomes
