"""Module entrypoint for running tokBot via ``python -m tokbot``."""

from .cli import run_cli


def main() -> None:
    """Execute the CLI and exit with its return code."""
    raise SystemExit(run_cli())


if __name__ == "__main__":  # pragma: no cover - module execution hook
    main()
