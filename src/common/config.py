"""Simple configuration helpers for tokBot."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple

from dotenv import dotenv_values


DEFAULT_ENVIRONMENT = "development"
DEFAULT_AGENT = "echo"
DEFAULT_AGENT_MODULES: Tuple[str, ...] = (
    "tokbot.agents.echo",
    "tokbot.agents.uppercase",
)


@dataclass(slots=True)
class Settings:
    """Container for environment-derived configuration."""

    environment: str = DEFAULT_ENVIRONMENT
    default_agent: str = DEFAULT_AGENT
    agent_modules: Tuple[str, ...] = DEFAULT_AGENT_MODULES

    @classmethod
    def from_env(cls, *, env_files: Iterable[str] | None = None) -> "Settings":
        """Build settings from environment variables, optionally loading a dotenv file."""

        env_overrides: dict[str, str] = {}
        if env_files:
            for candidate in env_files:
                candidate_path = Path(candidate)
                if candidate_path.is_file():
                    values = {
                        key: value
                        for key, value in dotenv_values(candidate_path).items()
                        if value is not None
                    }
                    env_overrides.update(values)

        def get_override(key: str) -> str | None:
            if key in os.environ:
                return os.environ[key]
            return env_overrides.get(key)

        def lookup(key: str, default: str) -> str:
            value = get_override(key)
            return value if value is not None else default

        raw_modules = get_override("TOKBOT_AGENT_MODULES")
        extra_modules: Tuple[str, ...] = ()
        if raw_modules:
            extra_modules = tuple(
                part.strip()
                for part in raw_modules.split(",")
                if part.strip()
            )

        deduped_modules = dict.fromkeys(DEFAULT_AGENT_MODULES + extra_modules)

        return cls(
            environment=lookup("TOKBOT_ENV", DEFAULT_ENVIRONMENT),
            default_agent=lookup("TOKBOT_DEFAULT_AGENT", DEFAULT_AGENT),
            agent_modules=tuple(deduped_modules.keys()),
        )
