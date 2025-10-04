# tokBot Project Status

This document summarizes the current state of the tokBot codebase, the features implemented, and how to use them.

## Implemented Features
- CLI entrypoint via `python -m tokbot` with commands:
  - `list`: Lists registered agents.
  - `run [agent] --message <text>`: Runs a specific agent or the default agent when omitted.
  - `workflow`: Runs the default sequence `planner -> builder -> auditor`, supports transcript output.
  - `issue read`: Reads a GitHub issue and recent comments (via `gh`).
  - `issue comment`: Posts a comment to a GitHub issue (via `gh`).
- Agents bundled:
  - `echo`, `uppercase`, `planner`, `builder`, `auditor`.
- Configuration via `.env` (or `--env-file`) with support for:
  - `TOKBOT_ENV`, `TOKBOT_DEFAULT_AGENT`, `TOKBOT_AGENT_MODULES`, `TOKBOT_TRANSCRIPTS_DIR`, `TOKBOT_GITHUB_REPO`.
- Transcript writing for workflows to `artifacts/transcripts` or a custom path.

## Recent Changes
- Added a `Makefile` with targets mirroring `requirements/start.json` commands for convenience.
- Updated dataclasses to be compatible with Python 3.9 by removing `slots=True` usage.

## Commands & Make Targets
Common actions are available through `make`:

```sh
# Setup
make venv && source .venv/bin/activate
make install-dev
make env

# Quality & tests
make lint
make format
make test
make test-cov

# CLI helpers
make list-agents
make run-default
make run-echo
make run-upper
make run-planner
make workflow
make issue-read
make issue-comment
make run-with-env
```

## Testing Status
- Unit tests for the CLI pass: `10 passed`.
- Coverage target available via `pytest --cov=tokbot --cov-report=term-missing`.

## Configuration Notes
- `requirements/start.json` references Python `3.11`. The project currently runs on Python `3.9` as well, and is compatible due to removal of `slots=True` in dataclasses.
- You can provide additional agent modules via `TOKBOT_AGENT_MODULES` (comma-separated module paths exposing `build_agent()`).

## Transcript Output
- Default directory: `artifacts/transcripts`.
- Override via `TOKBOT_TRANSCRIPTS_DIR`, or with CLI flags `--output`, `--namespace`, `--filename`.

## Suggested Next Steps
- Add more integrations under `src/tokbot/integrations/` (e.g., chat platforms or data sources).
- Expand agent implementations and document them in `AGENTS.md`.
- Add end-to-end tests for GitHub issue operations using a mocked `gh` runner.
- Consider pinning Python to `3.11` if desired; the codebase is compatible across versions.