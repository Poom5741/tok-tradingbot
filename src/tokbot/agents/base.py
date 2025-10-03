"""Base definitions for tokBot agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class Agent(Protocol):
    """Protocol describing a runnable agent."""

    name: str
    description: str

    def run(self, message: str) -> str:
        """Run the agent against an incoming message."""


@dataclass(slots=True)
class AgentResult:
    """Structured response from an agent invocation."""

    agent_name: str
    request: str
    response: str
