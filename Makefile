# =============================================================================
# Kompas Kompetencji – task orchestration
# Requires: GNU make + uv (https://docs.astral.sh/uv/)
# Windows: run from Git Bash, or install make (`winget install GnuWin32.Make`).
# =============================================================================

UV        ?= uv
UV_RUN    := $(UV) run --no-sync
PY        := $(UV_RUN) python
SRC       := src/kompas
HOST      ?= 127.0.0.1
PORT      ?= 8000
ENV       ?= dev
MATERIALS ?= [Ministerstwo Cyfryzacji - Biuro Dyrektora generalnego] Kompas Kompetencji

.DEFAULT_GOAL := help
.PHONY: help install install-ml install-import hooks run dev serve test test-unit test-integration \
        cov lint format typecheck check pre-commit kb import-model verify clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ----------------------------------------------------------------------------- setup
install: ## Create venv and install runtime + dev dependencies
	$(UV) sync --extra dev

install-ml: ## Install optional neural embedding backend (sentence-transformers)
	$(UV) sync --extra dev --extra ml

install-import: ## Install tooling for importing xlsx/docx source materials
	$(UV) sync --extra dev --extra import

hooks: ## Install pre-commit git hooks
	$(UV) run pre-commit install --install-hooks
	$(UV) run pre-commit install --hook-type pre-push

# Target-specific exports work regardless of the shell make uses (sh / cmd).
run serve: export KOMPAS_ENV = $(ENV)
dev: export KOMPAS_ENV = dev
test test-unit test-integration cov verify: export KOMPAS_ENV = test

# ----------------------------------------------------------------------------- run
run: ## Run API (uvicorn) using config/environments/$(ENV).yaml
	$(UV_RUN) uvicorn kompas.main:app --host $(HOST) --port $(PORT)

dev: ## Run API with auto-reload
	$(UV_RUN) uvicorn kompas.main:app --host $(HOST) --port $(PORT) --reload --reload-dir src --reload-dir config

serve: ## Run API through the package entry point (reads server section of config)
	$(PY) -m kompas

# ----------------------------------------------------------------------------- quality
test: ## Run full test-suite
	$(UV_RUN) pytest

test-unit: ## Run unit tests only
	$(UV_RUN) pytest -m "not integration"

test-integration: ## Run API integration tests only
	$(UV_RUN) pytest -m integration

cov: ## Run tests with coverage report (fails under threshold from pyproject)
	$(UV_RUN) pytest --cov --cov-report=term-missing --cov-report=html:docs/coverage

lint: ## Ruff lint
	$(UV) run ruff check src tests scripts

format: ## Ruff format + autofix
	$(UV) run ruff format src tests scripts
	$(UV) run ruff check --fix src tests scripts

typecheck: ## Mypy static typing
	$(UV) run mypy

check: lint typecheck cov ## Lint + types + tests with coverage

pre-commit: ## Run all pre-commit hooks against all files
	$(UV) run pre-commit run --all-files

# ----------------------------------------------------------------------------- data / models
kb: ## Build knowledge base text corpus + retrieval index (data/knowledge_base -> models/index)
	$(PY) scripts/build_knowledge_base.py --materials "$(MATERIALS)" --include-pdfs

import-model: ## Re-generate data/competency_model/*.yaml from Model_kompetencji.xlsx
	$(UV) run --extra import python scripts/import_competency_model.py --materials "$(MATERIALS)"

verify: ## Smoke-test: run the demo scenario from data/samples end-to-end (no server needed)
	$(PY) scripts/run_demo_scenario.py

clean: ## Remove caches and build artefacts
	$(PY) scripts/clean.py
