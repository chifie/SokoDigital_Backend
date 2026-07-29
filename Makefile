# ═══════════════════════════════════════════════════════════════════════════════
#  SokoDigital API — Makefile
# ═══════════════════════════════════════════════════════════════════════════════

.DEFAULT_GOAL := help

PYTHON     := python
PIP        := pip
PYTEST     := python -m pytest
RUFF       := ruff
MYPY       := mypy
ALEMBIC    := alembic
DOCKER     := docker
DOCKER_COMPOSE := docker compose
TEST_FLAGS := -v --tb=short -k "not test_email_verification"

.PHONY: help install install-dev lint typecheck test test-all \  # help
        test-e2e test-e2e-down precommit-install precommit-run \ # testing
        migrate migrate-autogen migrate-show migrate-down \      # database
        seed docker-up docker-down docker-build \                # docker
        clean format                                             # tools


# ── Help ─────────────────────────────────────────────────────────────────────

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'


# ── Installation ─────────────────────────────────────────────────────────────

install: ## Install production dependencies
	$(PIP) install -r requirements.txt

install-dev: install ## Install dev dependencies (testing, linting)
	$(PIP) install ruff mypy


# ── Lint & Type-check ───────────────────────────────────────────────────────

lint: ## Run Ruff linter
	$(RUFF) check app/ tests/

format: ## Auto-format code with Ruff
	$(RUFF) check app/ tests/ --fix
	$(RUFF) format app/ tests/

typecheck: ## Run mypy type checker
	$(MYPY) app/ --ignore-missing-imports || true


# ── Testing ──────────────────────────────────────────────────────────────────

test: ## Run unit tests (skips integration tests needing a database)
	$(PYTEST) tests/ $(TEST_FLAGS)

test-all: ## Run all tests (unit + integration; requires running PostgreSQL)
	$(PYTEST) tests/ -v --tb=short

test-e2e: ## Run full test suite in Docker (isolated, ephemeral, reproducible)
	$(DOCKER_COMPOSE) -f docker-compose.test.yml up --build \
		--abort-on-container-exit --exit-code-from test-runner

test-e2e-down: ## Tear down the E2E test infrastructure and clean volumes
	$(DOCKER_COMPOSE) -f docker-compose.test.yml down --volumes


# ── Pre-commit hooks ─────────────────────────────────────────────────────────

precommit-install: ## Install pre-commit hooks
	pre-commit install

precommit-run: ## Run pre-commit hooks on all files
	pre-commit run --all-files


# ── Database Migrations ──────────────────────────────────────────────────────

migrate: ## Apply pending migrations
	$(ALEMBIC) upgrade head

migrate-autogen: ## Auto-generate a new migration from model changes
	@read -p "Migration message: " msg; \
	$(ALEMBIC) revision --autogenerate -m "$$msg"

migrate-show: ## Show migration history
	$(ALEMBIC) history

migrate-down: ## Roll back the last migration
	$(ALEMBIC) downgrade -1

seed: ## Apply seed data migration
	$(ALEMBIC) upgrade a1b2c3d4e5f6


# ── Docker ───────────────────────────────────────────────────────────────────

docker-up: ## Start all services (db, redis, api, worker)
	$(DOCKER_COMPOSE) up -d --build

docker-down: ## Stop all services
	$(DOCKER_COMPOSE) down

docker-build: ## Build images without starting
	$(DOCKER_COMPOSE) build

docker-logs: ## Tail logs from all services
	$(DOCKER_COMPOSE) logs -f

docker-shell: ## Open a shell in the API container
	$(DOCKER_COMPOSE) exec api bash


# ── Cleanup ──────────────────────────────────────────────────────────────────

clean: ## Remove Python cache, build artifacts, and test cache
	rm -rf __pycache__ .pytest_cache .mypy_cache *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
