.PHONY: install dev run test lint clean

install: ## Install production dependencies
	uv sync

dev: ## Install all dependencies (including dev)
	uv sync --all-extras

run: ## Start the FastAPI server (with hot-reload)
	uv run python main.py

test: ## Run the test suite
	uv run pytest -v

lint: ## Run the linter
	uv run ruff check src/ tests/

format: ## Auto-format code
	uv run ruff format src/ tests/

clean: ## Remove generated artifacts
	rm -rf __pycache__ .pytest_cache data/schedules.csv
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
