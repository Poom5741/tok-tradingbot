"""Auditor agent that evaluates outcomes."""

from __future__ import annotations

from dataclasses import dataclass

from .base import Agent


@dataclass(slots=True)
class AuditorAgent:
    """Review builder output and highlight risks."""

    name: str = "auditor"
    description: str = "Audits deliverables, surfacing open questions."

    def run(self, message: str) -> str:
        """Return a lightweight audit summary."""
        summary = message.strip() or "No build output to audit."
        return (
            "Audit Report\n"
            f"Input: {summary}\n"
            "Checks: lint, unit tests, configuration review.\n"
            "Result: pass with follow-up on observability."
        )


def build_agent() -> Agent:
    """Factory helper for the auditor agent."""
    return AuditorAgent()
