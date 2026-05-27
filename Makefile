.PHONY: help install install-package install-updates list-outdated lint-check lint-fix type-check test test-integration

help:
	@echo "Available commands:"
	@echo "  make lint-check        - Run ruff linter checks"
	@echo "  make lint-fix          - Run ruff linter with fixes and formatting"
	@echo "  make type-check        - Run pyrefly type checker"
	@echo "  make test              - Run pytest tests (requires Docker)"
	@echo "  make test-integration  - Run end-to-end integration tests with mock services (requires Docker)"

install:
	@ pip install uv
	@ uv sync --all-extras

install-updates:
	@ pip install uv
	@ uv sync --upgrade --refresh --all-extras

install-package:
	@ uv pip install -e .

list-outdated: install
	@ pip list -o

lint-check:
	@ uv run ruff check . --exclude .env

lint-fix:
	@ uv run ruff check . --fix --exclude .env
	@ uv run ruff format . --exclude .env

type-check:
	@ uv run pyrefly check

test:
	@ uv run pytest tests/


test-integration:
	@ docker compose --profile integration up --build --abort-on-container-exit --exit-code-from integration-test-runner

test-integration-run:
	@ uv run pytest tests_integration/
