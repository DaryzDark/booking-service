.DEFAULT_GOAL := help
.PHONY: help dev down logs test lint 

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'


dev: ## Build and start the whole stack 
	docker compose up --build

down: ## Stop the stack and remove volumes
	docker compose down -v

logs: ## Tail logs from all services
	docker compose logs -f

test: ## Run the test suite 
	uv run pytest

lint: ## Lint and check formatting
	uv run ruff check .
	uv run ruff format --check .


