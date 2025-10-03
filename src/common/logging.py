"""Central logging configuration for tokBot."""

from __future__ import annotations

import logging
from logging import Logger


def configure_logging(level: int = logging.INFO) -> Logger:
    """Configure and return a root logger for use across the project."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    return logging.getLogger("tokbot")
