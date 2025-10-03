"""Utilities for persisting workflow transcripts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from common import Settings

from .agents.base import AgentResult


def write_transcript(
    results: Sequence[AgentResult],
    settings: Settings,
    *,
    output_path: str | Path | None = None,
    metadata: dict[str, str] | None = None,
) -> Path:
    """Persist a workflow transcript to disk and return the file path."""
    destination = _resolve_destination(settings, output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": settings.environment,
        "agents": [result.agent_name for result in results],
        "metadata": metadata or {},
        "entries": [
            {
                "agent": result.agent_name,
                "request": result.request,
                "response": result.response,
            }
            for result in results
        ],
    }

    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return destination


def _resolve_destination(settings: Settings, output_path: str | Path | None) -> Path:
    if output_path:
        return Path(output_path)

    return settings.transcripts_dir / f"workflow_{_timestamp_token()}.json"


def _timestamp_token() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
