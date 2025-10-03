"""Core orchestration logic for tokBot."""

from __future__ import annotations

from dataclasses import dataclass

from common import Settings
from .agents.base import AgentResult
from .agents.registry import AgentRegistry


@dataclass(slots=True)
class TokBotOrchestrator:
    """Coordinate agent selection and execution."""

    registry: AgentRegistry
    settings: Settings

    def run(self, *, agent_name: str | None = None, message: str = "") -> AgentResult:
        """Execute the requested agent with the provided message."""
        target = agent_name or self.settings.default_agent
        agent = self.registry.get(target)
        response = agent.run(message)
        return AgentResult(agent_name=agent.name, request=message, response=response)

    def run_sequence(
        self,
        agent_names: list[str] | tuple[str, ...],
        message: str,
    ) -> list[AgentResult]:
        """Execute multiple agents sequentially, feeding each the prior response."""
        results: list[AgentResult] = []
        current = message
        for name in agent_names:
            result = self.run(agent_name=name, message=current)
            results.append(result)
            current = result.response
        return results
