"""Configuration helpers for the microstructure bot (paper trading)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Optional

from dotenv import dotenv_values


DEFAULT_ENVIRONMENT = "development"
DEFAULT_FT_MIN = 1.8
DEFAULT_IP_MIN_BPS = 5.0
DEFAULT_SE_MIN = 0.1
DEFAULT_SE_MAX = 2.0


@dataclass
class Settings:
    """Container for environment-derived configuration for the bot."""

    environment: str = DEFAULT_ENVIRONMENT
    ft_min: float = DEFAULT_FT_MIN
    ip_min_bps: float = DEFAULT_IP_MIN_BPS
    se_min: float = DEFAULT_SE_MIN
    se_max: float = DEFAULT_SE_MAX
    github_repo: Optional[str] = None

    @classmethod
    def from_env(cls, *, env_files: Iterable[str] | None = None) -> "Settings":
        """Build settings from environment variables, optionally loading a dotenv file."""

        env_overrides: dict[str, str] = {}
        if env_files:
            for candidate in env_files:
                candidate_path = os.path.abspath(candidate)
                if os.path.isfile(candidate_path):
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

        def lookup_optional(key: str) -> Optional[str]:
            value = get_override(key)
            if value is None:
                return None
            stripped = value.strip()
            return stripped or None

        return cls(
            environment=lookup("TOKBOT_ENV", DEFAULT_ENVIRONMENT),
            ft_min=float(lookup("TOKBOT_FT_MIN", str(DEFAULT_FT_MIN))),
            ip_min_bps=float(lookup("TOKBOT_IP_MIN_BPS", str(DEFAULT_IP_MIN_BPS))),
            se_min=float(lookup("TOKBOT_SE_MIN", str(DEFAULT_SE_MIN))),
            se_max=float(lookup("TOKBOT_SE_MAX", str(DEFAULT_SE_MAX))),
            github_repo=lookup_optional("TOKBOT_GITHUB_REPO"),
        )
