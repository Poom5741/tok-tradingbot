"""Agent that transforms messages to uppercase."""

from __future__ import annotations

from dataclasses import dataclass

from .base import Agent


@dataclass(slots=True)
class UppercaseAgent:
    """Convert inbound messages into uppercase text."""

    name: str = "uppercase"
    description: str = "Transforms the incoming message to uppercase."

    def run(self, message: str) -> str:
        """Return the message in uppercase form."""
        cleaned = message.strip()
        return cleaned.upper() if cleaned else "(no content)"


def build_agent() -> Agent:
    """Factory helper for the uppercase agent."""
    return UppercaseAgent()
