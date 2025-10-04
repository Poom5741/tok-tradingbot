SHELL := /bin/bash

# Prefer virtualenv binaries when available
PY      := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python)
PIP     := $(shell [ -x .venv/bin/pip ] && echo .venv/bin/pip || echo pip)
PYTEST  := $(shell [ -x .venv/bin/pytest ] && echo .venv/bin/pytest || echo pytest)
RUFF    := $(shell [ -x .venv/bin/ruff ] && echo .venv/bin/ruff || echo ruff)

.PHONY: help venv install-dev install-prod env lint format test test-cov \
        list-agents run-default run-echo run-upper run-planner workflow \
        issue-read issue-comment run-with-env

.DEFAULT_GOAL := help

help:
	@echo "Targets:"
	@echo "  venv          Create virtualenv in .venv"
	@echo "  install-dev   Install dev dependencies"
	@echo "  install-prod  Install base dependencies"
	@echo "  env           Copy .env.example to .env"
	@echo "  lint          Run ruff check"
	@echo "  format        Run ruff format"
	@echo "  test          Run pytest"
	@echo "  test-cov      Run pytest with coverage"
	@echo "  list-agents   List available agents"
	@echo "  run-default   Run default agent with 'Ping'"
	@echo "  run-echo      Run echo agent"
	@echo "  run-upper     Run uppercase agent"
	@echo "  run-planner   Run planner agent"
	@echo "  workflow      Run demo workflow and write transcript"
	@echo "  issue-read    Read issue 123 from owner/repo"
	@echo "  issue-comment Comment 'Agent update' to issue 123"
	@echo "  run-with-env  Run with .env loaded"

venv:
	$(PY) -m venv .venv
	@echo "Activate with: source .venv/bin/activate"

install-dev:
	$(PIP) install -r requirements/dev.txt

install-prod:
	$(PIP) install -r requirements/base.txt

env:
	cp .env.example .env

lint:
	$(RUFF) check src tests

format:
	$(RUFF) format src tests

test:
	$(PYTEST)

test-cov:
	$(PYTEST) --cov=tokbot --cov-report=term-missing

list-agents:
	$(PY) -m tokbot list

run-default:
	$(PY) -m tokbot run --message 'Ping'

run-echo:
	$(PY) -m tokbot run echo --message 'Hello'

run-upper:
	$(PY) -m tokbot run uppercase --message 'Hello'

run-planner:
	$(PY) -m tokbot run planner --message 'Outline feature'

workflow:
	$(PY) -m tokbot workflow --message 'Ship feature' --namespace demo --filename summary --meta issue=123 --meta priority=high

issue-read:
	$(PY) -m tokbot issue read --issue 123 --repo owner/repo

issue-comment:
	$(PY) -m tokbot issue comment --issue 123 --body 'Agent update'

run-with-env:
	$(PY) -m tokbot --env-file .env run --message 'Ping'