"""Registry for managing tokBot agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable

from .base import Agent


@dataclass(slots=True)
class AgentRegistry:
    """In-memory store of registered agents."""

    _agents: Dict[str, Agent]

    def __init__(self) -> None:
        self._agents = {}

    def register(self, agent: Agent) -> None:
        """Register a new agent by its canonical name."""
        key = agent.name.lower()
        self._agents[key] = agent

    def get(self, name: str) -> Agent:
        """Retrieve an agent by name, raising ``KeyError`` when missing."""
        key = name.lower()
        if key not in self._agents:
            raise KeyError(f"Agent '{name}' is not registered.")
        return self._agents[key]

    def keys(self) -> Iterable[str]:
        """Return a view of registered agent names."""
        return self._agents.keys()

    def values(self) -> Iterable[Agent]:
        """Return an iterable of the registered agents."""
        return self._agents.values()
