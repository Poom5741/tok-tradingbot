"""Runtime package for tokBot automation orchestrator."""

from importlib import metadata


try:
    __version__ = metadata.version("tokbot")
except metadata.PackageNotFoundError:  # pragma: no cover - not installed
    __version__ = "0.1.0"

__all__ = ["__version__"]
