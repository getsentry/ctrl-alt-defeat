.PHONY: help develop sync test server clean direnv-help

help:
	@echo "Available commands:"
	@echo "  make develop    - Setup development environment"
	@echo "  make sync       - Sync dependencies using devenv"
	@echo "  make test       - Run all tests"
	@echo "  make server     - Start the FastAPI server"
	@echo "  make clean      - Clean up generated files"
	@echo "  make direnv-help - Show direnv help"

develop: sync
	@echo "Development environment ready!"

sync:
	@if [ -f ".venv/bin/python" ]; then \
		.venv/bin/python devenv/sync.py; \
	else \
		python3 devenv/sync.py; \
	fi

test:
	@if [ -f ".venv/bin/python" ]; then \
		cd server && ../.venv/bin/python -m pytest -v; \
	else \
		cd server && python -m pytest -v; \
	fi

server:
	@if [ -f ".venv/bin/python" ]; then \
		cd server && ../.venv/bin/python main.py; \
	else \
		cd server && python main.py; \
	fi

clean:
	@echo "Cleaning up..."
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type f -name ".coverage" -delete 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean complete!"

direnv-help:
	@echo "Direnv Help for Autobattler"
	@echo "============================"
	@echo ""
	@echo "Direnv automatically loads environment variables and activates the Python virtual environment."
	@echo ""
	@echo "Common commands:"
	@echo "  direnv allow    - Allow direnv to load the .envrc file"
	@echo "  direnv reload   - Reload the environment"
	@echo "  direnv deny     - Prevent direnv from loading"
	@echo ""
	@echo "If you see errors:"
	@echo "  1. Run 'make sync' to install dependencies"
	@echo "  2. Run 'direnv allow' to reload the environment"
	@echo ""
	@echo "To use devenv for dependency management:"
	@echo "  1. Install devenv: https://github.com/getsentry/devenv#install"
	@echo "  2. Run 'devenv sync' to sync all dependencies"
