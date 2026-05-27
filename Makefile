.PHONY: install test lint local-up local-down

install:
	pip install -r requirements-dev.txt

test:
	pytest tests/unit -v --cov=src --cov-report=term-missing

lint:
	ruff check src tests

local-up:
	docker compose up -d
	@echo "DynamoDB Local ready on http://localhost:8000"

local-down:
	docker compose down

local-list-tables:
	aws dynamodb list-tables \
		--endpoint-url http://localhost:8000 \
		--region eu-south-1 \
		--no-cli-pager
