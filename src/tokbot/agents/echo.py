"""Simple echo agent for local testing."""

from __future__ import annotations

from dataclasses import dataclass

from .base import Agent


@dataclass(slots=True)
class EchoAgent:
    """Reflect text back to the caller with a short prefix."""

    name: str = "echo"
    description: str = "Repeats the incoming message for debugging."

    def run(self, message: str) -> str:
        """Return a friendly acknowledgement of the inbound message."""
        cleaned = message.strip() or "(no content)"
        return f"Echoing: {cleaned}"


def build_agent() -> Agent:
    """Factory helper for registries to instantiate the echo agent."""
    return EchoAgent()
