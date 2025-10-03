"""Builder agent that emits implementation steps."""

from __future__ import annotations

from dataclasses import dataclass

from .base import Agent


@dataclass(slots=True)
class BuilderAgent:
    """Translate plans into concrete implementation tasks."""

    name: str = "builder"
    description: str = "Proposes implementation tasks and validation commands."

    def run(self, message: str) -> str:
        """Return a build checklist based on the prior plan output."""
        context = message.strip() or "Plan missing"
        return (
            "Build Checklist\n"
            f"Context: {context}\n"
            "Tasks: implement feature, add tests, update docs.\n"
            "Validation: run ruff check and pytest.\n"
            "Deliverable: open PR referencing the issue."
        )


def build_agent() -> Agent:
    """Factory helper for the builder agent."""
    return BuilderAgent()
