# Repository Guidelines

The tokBot project is being built as a modular automation agent; this guide keeps contributions consistent while the codebase is maturing.

## Project Structure & Module Organization
Create a `src/` package for runtime code, grouping features by integration (e.g., `src/telegram/`, `src/trading/`). Place shared utilities in `src/common/` and keep orchestration logic in `src/tokbot/__main__.py`. Agents live under `src/tokbot/agents/`, each exposing a `build_agent()` factory (defaults ship with `echo`, `uppercase`, `planner`, `builder`, `auditor`). Tests shadow their modules in `tests/` with identical package paths. Prompt templates, sample payloads, and other static assets belong in `assets/`, while workflow transcripts default to `artifacts/transcripts/`. The existing `requirements/` directory should be extended with `base.txt` for runtime dependencies and `dev.txt` for tooling; regenerate compiled locks as needed.

## Build, Test, and Development Commands
Target Python 3.11. Set up the environment with `python -m venv .venv && source .venv/bin/activate`, then `pip install -r requirements/dev.txt`. Run `ruff check src tests` to lint and `pytest` for unit and integration coverage. Launch the bot locally with `python -m tokbot` (or the module housing your entrypoint) and include a `.env.example` describing required secrets. Set `TOKBOT_GITHUB_REPO` to point at your remote (e.g., `owner/repo`) and use `python -m tokbot issue read --issue 123` / `python -m tokbot issue comment --issue 123 --body "Update"` to sync agent context from GitHub issues. Use `python -m tokbot workflow --message "Ship feature" --namespace demo --filename summary --meta issue=123 --meta priority=high` to exercise the planner→builder→auditor loop and persist transcripts, and `python -m tokbot --env-file .env run --message "Ping"` to validate configuration overrides. Use `pip install -r requirements/base.txt` in production workflows.

## Coding Style & Naming Conventions
Follow PEP 8 with 4-space indentation and descriptive module names (`interaction_service.py`, not `utils2.py`). Require type hints, and prefer dataclasses for structured payloads. Public APIs adopt snake_case for functions, UpperCamelCase for classes, and UPPER_CASE for constants. Apply `ruff --fix` before opening a PR; use `black` only when formatting cannot be expressed via `ruff format`.

## Testing Guidelines
Author granular unit tests that mirror module names (`tests/telegram/test_webhook.py`). Keep fixtures under `tests/conftest.py` and mark costly tests with `@pytest.mark.slow`. Maintain ≥85% coverage; verify with `pytest --cov=tokbot --cov-report=term-missing`. Document integration test setup alongside the test module if it requires external services.

## Commit & Pull Request Guidelines
Commits follow `type(scope): short summary` (e.g., `feat(telegram): add webhook handler`). Keep bodies wrapped at 72 characters and reference issues with `Refs #123`. PRs must state intent, list validation commands, attach logs or screenshots for user-visible changes, and note configuration updates. Request review once CI passes and ensure secrets are never committed.
