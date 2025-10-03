"""Planner agent that produces structured work plans."""

from __future__ import annotations

from dataclasses import dataclass

from .base import Agent


@dataclass(slots=True)
class PlannerAgent:
    """Draft high-level plans for incoming objectives."""

    name: str = "planner"
    description: str = "Breaks down a request into objectives, risks, and next steps."

    def run(self, message: str) -> str:
        """Return a templated planning artifact."""
        goal = message.strip() or "(no stated objective)"
        return (
            "Plan\n"
            f"Objective: {goal}\n"
            "Approach: Outline quick win followed by hardening.\n"
            "Tests: Define unit tests for critical paths.\n"
            "Risks: Missing configuration or external dependencies.\n"
            "Next: hand off to builder with task list."
        )


def build_agent() -> Agent:
    """Factory helper for the planner agent."""
    return PlannerAgent()
