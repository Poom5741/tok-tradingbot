SHELL := /bin/bash

# Prefer virtualenv binaries when available
PY      := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)
PIP     := $(shell [ -x .venv/bin/pip ] && echo .venv/bin/pip || echo python3 -m pip)
PYTEST  := $(shell [ -x .venv/bin/pytest ] && echo .venv/bin/pytest || echo pytest)
RUFF    := $(shell [ -x .venv/bin/ruff ] && echo .venv/bin/ruff || echo ruff)

# Runtime configuration
PYTHONPATH ?= src
ENV_FILE    ?= .env
# Paper default: small finite run; Live default: infinite (Ctrl+C to stop)
LOOPS       ?= 2
LIVE_LOOPS  ?= 0
DEX         ?= uniswap-v2
FEE_BPS     ?= 3000

.PHONY: help venv install install-dev install-prod env lint format test test-cov \
        telegram paper paper-pair live issue-read issue-comment

.DEFAULT_GOAL := help

help:
	@echo "Targets:"
	@echo "  venv          Create virtualenv in .venv"
	@echo "  install       Install base dependencies"
	@echo "  install-dev   Install dev dependencies"
	@echo "  env           Copy .env.example to .env"
	@echo "  telegram      Start Telegram bot (uses ENV_FILE)"
	@echo "  paper         Run paper-trading loop (set LOOPS)"
	@echo "  paper-pair    Run paper with pair resolution (set TOKEN0,TOKEN1, DEX, FEE_BPS)"
	@echo "  live          Run live mode (DRY-RUN; set LIVE_LOOPS)"
	@echo "  lint          Run ruff check"
	@echo "  format        Run ruff format"
	@echo "  test          Run pytest"
	@echo "  test-cov      Run pytest with coverage"
	@echo "  issue-read    Read issue 123 from owner/repo"
	@echo "  issue-comment Comment 'Agent update' to issue 123"

venv:
	$(PY) -m venv .venv
	@echo "Activate with: source .venv/bin/activate"

install: install-prod

install-dev:
	$(PIP) install -r requirements/dev.txt

install-prod:
	$(PIP) install -r requirements/base.txt

env:
	cp .env.example .env

telegram:
	PYTHONPATH=$(PYTHONPATH) $(PY) -m tokbot --env-file $(ENV_FILE) telegram

paper:
	PYTHONPATH=$(PYTHONPATH) $(PY) -m tokbot paper --loops $(LOOPS)

paper-pair:
	@if [ -z "$(TOKEN0)" ] || [ -z "$(TOKEN1)" ]; then \
		echo "Set TOKEN0 and TOKEN1 to ERC20 addresses"; exit 1; \
	fi
	PYTHONPATH=$(PYTHONPATH) $(PY) -m tokbot paper --loops $(LOOPS) --token0 $(TOKEN0) --token1 $(TOKEN1) --dex $(DEX) --fee-bps $(FEE_BPS)

live:
	PYTHONPATH=$(PYTHONPATH) $(PY) -m tokbot --env-file $(ENV_FILE) live --loops $(LIVE_LOOPS)

lint:
	$(RUFF) check src tests || true

format:
	$(RUFF) format src tests || true

test:
	$(PYTEST) || true

test-cov:
	$(PYTEST) --cov=tokbot --cov-report=term-missing || true

issue-read:
	PYTHONPATH=$(PYTHONPATH) $(PY) -m tokbot issue read --issue 123 --repo owner/repo

issue-comment:
	PYTHONPATH=$(PYTHONPATH) $(PY) -m tokbot issue comment --issue 123 --body 'Agent update'