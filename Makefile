.PHONY: help setup-secrets run-test clean

help:
	@echo "🎯 Communication Tool - Available Commands"
	@echo "==========================================="
	@echo ""
	@echo "Setup:"
	@echo "  make setup-secrets    Setup GitHub Secrets from .env.local"
	@echo "  make setup-local      Copy .env.secrets to .env.local"
	@echo ""
	@echo "Development:"
	@echo "  make install          Install Python dependencies"
	@echo "  make run-local        Run locally (after .env.local setup)"
	@echo ""
	@echo "Testing:"
	@echo "  make test             Run unit tests"
	@echo "  make lint             Run code linting"
	@echo ""
	@echo "CI/CD:"
	@echo "  make run-workflow     Trigger GitHub Action manually"
	@echo "  make check-secrets    List GitHub Secrets"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean            Remove __pycache__, .pyc files"
	@echo ""

setup-local:
	@if [ ! -f .env.local ]; then \
		cp .env.secrets .env.local; \
		echo "✅ Created .env.local from template"; \
		echo "📝 Edit .env.local and fill in your API keys"; \
	else \
		echo "✅ .env.local already exists"; \
	fi

setup-secrets: setup-local
	@bash scripts/setup-secrets.sh

install:
	pip install -r requirements.txt

run-local:
	@if [ ! -f .env.local ]; then \
		echo "❌ .env.local not found. Run: make setup-local"; \
		exit 1; \
	fi
	@echo "🚀 Running Communication Tool locally..."
	@. .env.local && python3 -m src.main

test:
	pytest tests/ -v

lint:
	black --check src/
	python3 -m pylint src/ --disable=W0212,R0913

run-workflow:
	@echo "🚀 Triggering GitHub Action..."
	@if command -v gh &> /dev/null; then \
		gh workflow run manual-trigger.yml; \
		echo "✅ Workflow triggered. Check: https://github.com/haimk-max/my-first-project/actions"; \
	else \
		echo "❌ GitHub CLI not installed. Install: https://cli.github.com"; \
	fi

check-secrets:
	@echo "🔍 Checking GitHub Secrets..."
	@if command -v gh &> /dev/null; then \
		gh secret list; \
	else \
		echo "❌ GitHub CLI not installed."; \
		echo "Check manually at: https://github.com/haimk-max/my-first-project/settings/secrets/actions"; \
	fi

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	echo "✅ Cleaned up Python cache files"
