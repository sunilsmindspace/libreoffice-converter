# Makefile for LibreOffice Document Converter

# Variables
PYTHON = python3
PIP = pip3
PYTHON_VERSION = 3.13
VENV = venv
VENV_BIN = $(VENV)/bin
APP_NAME = libreoffice-converter
DOCKER_IMAGE = $(APP_NAME):latest
DOCKER_REGISTRY ?= 
DOCKER_REPO ?= $(APP_NAME)
VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
BUILD_DATE = $(shell date -u +'%Y-%m-%dT%H:%M:%SZ')
GIT_COMMIT = $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")
GIT_BRANCH = $(shell git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

# Colors
RED = \033[0;31m
GREEN = \033[0;32m
YELLOW = \033[1;33m
BLUE = \033[0;34m
NC = \033[0m # No Color

.PHONY: help install install-dev setup test test-unit test-integration test-coverage clean docker-build docker-run docker-stop docker-push docker-tag docker-release lint format check-format type-check dev run logs version

# Default target
help: ## Show this help message
	@echo "$(BLUE)LibreOffice Document Converter - Available Commands$(NC)"
	@echo
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'

# Setup and Installation
setup: ## Run the complete setup process
	@echo "$(BLUE)Running setup...$(NC)"
	@chmod +x scripts/setup.sh
	@./scripts/setup.sh

install: ## Install production dependencies
	@echo "$(BLUE)Installing production dependencies...$(NC)"
	@$(PIP) install -r requirements.txt

install-dev: ## Install development dependencies
	@echo "$(BLUE)Installing development dependencies...$(NC)"
	@$(PIP) install -r requirements-dev.txt

venv: ## Create virtual environment
	@echo "$(BLUE)Creating virtual environment...$(NC)"
	@$(PYTHON) -c "import sys; exit(0 if sys.version_info >= (3,11) else 1)" || (echo "$(RED)Python 3.11+ required$(NC)" && exit 1)
	@$(PYTHON) -m venv $(VENV)
	@echo "$(GREEN)Virtual environment created. Activate with: source $(VENV_BIN)/activate$(NC)"

# Testing
test: ## Run all tests
	@echo "$(BLUE)Running all tests...$(NC)"
	@chmod +x scripts/test.sh
	@./scripts/test.sh all

test-unit: ## Run unit tests only
	@echo "$(BLUE)Running unit tests...$(NC)"
	@chmod +x scripts/test.sh
	@./scripts/test.sh unit

test-integration: ## Run integration tests only
	@echo "$(BLUE)Running integration tests...$(NC)"
	@chmod +x scripts/test.sh
	@./scripts/test.sh integration

test-coverage: ## Run tests with coverage report
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	@chmod +x scripts/test.sh
	@./scripts/test.sh coverage

test-quick: ## Run quick unit tests only
	@echo "$(BLUE)Running quick tests...$(NC)"
	@chmod +x scripts/test.sh
	@./scripts/test.sh quick

# Code Quality
lint: ## Run linting
	@echo "$(BLUE)Running linting...$(NC)"
	@flake8 app.py tests/ --max-line-length=120 --ignore=E501,W503
	@echo "$(GREEN)Linting completed$(NC)"

format: ## Format code with black
	@echo "$(BLUE)Formatting code...$(NC)"
	@black app.py tests/ --line-length=120
	@isort app.py tests/ --profile black
	@echo "$(GREEN)Code formatting completed$(NC)"

check-format: ## Check code formatting without making changes
	@echo "$(BLUE)Checking code formatting...$(NC)"
	@black --check app.py tests/ --line-length=120
	@isort --check-only app.py tests/ --profile black
	@echo "$(GREEN)Code formatting check completed$(NC)"

type-check: ## Run type checking
	@echo "$(BLUE)Running type checking...$(NC)"
	@mypy app.py --ignore-missing-imports
	@echo "$(GREEN)Type checking completed$(NC)"

# Development
dev: install-dev ## Setup development environment
	@echo "$(GREEN)Development environment ready$(NC)"

run: ## Run the application locally
	@echo "$(BLUE)Starting application...$(NC)"
	@$(PYTHON) app.py

run-dev: ## Run the application in development mode
	@echo "$(BLUE)Starting application in development mode...$(NC)"
	@uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Docker
# Docker
docker-build: ## Build Docker image
	@echo "$(BLUE)Building Docker image...$(NC)"
	@docker build \
		--build-arg BUILD_DATE="$(BUILD_DATE)" \
		--build-arg VERSION="$(VERSION)" \
		--build-arg GIT_COMMIT="$(GIT_COMMIT)" \
		--build-arg GIT_BRANCH="$(GIT_BRANCH)" \
		-t $(APP_NAME):$(VERSION) \
		-t $(APP_NAME):latest \
		.
	@echo "$(GREEN)Docker image built successfully$(NC)"
	@echo "$(YELLOW)Built images:$(NC)"
	@echo "  $(APP_NAME):$(VERSION)"
	@echo "  $(APP_NAME):latest"

docker-tag: ## Tag Docker image for registry
	@if [ -z "$(DOCKER_REGISTRY)" ]; then \
		echo "$(RED)Error: DOCKER_REGISTRY not set$(NC)"; \
		echo "$(YELLOW)Usage: make docker-tag DOCKER_REGISTRY=your-registry.com$(NC)"; \
		exit 1; \
	fi
	@echo "$(BLUE)Tagging Docker image for registry...$(NC)"
	@docker tag $(APP_NAME):$(VERSION) $(DOCKER_REGISTRY)/$(DOCKER_REPO):$(VERSION)
	@docker tag $(APP_NAME):$(VERSION) $(DOCKER_REGISTRY)/$(DOCKER_REPO):latest
	@echo "$(GREEN)Images tagged successfully:$(NC)"
	@echo "  $(DOCKER_REGISTRY)/$(DOCKER_REPO):$(VERSION)"
	@echo "  $(DOCKER_REGISTRY)/$(DOCKER_REPO):latest"

docker-push: docker-build docker-tag ## Push Docker image to registry
	@if [ -z "$(DOCKER_REGISTRY)" ]; then \
		echo "$(RED)Error: DOCKER_REGISTRY not set$(NC)"; \
		echo "$(YELLOW)Usage: make docker-push DOCKER_REGISTRY=your-registry.com [DOCKER_REPO=custom-name] [VERSION=1.0.0]$(NC)"; \
		echo "$(YELLOW)Examples:$(NC)"; \
		echo "  make docker-push DOCKER_REGISTRY=docker.io/myuser"; \
		echo "  make docker-push DOCKER_REGISTRY=ghcr.io/myorg DOCKER_REPO=my-converter"; \
		echo "  make docker-push DOCKER_REGISTRY=myregistry.com VERSION=v1.2.3"; \
		exit 1; \
	fi
	@echo "$(BLUE)Pushing Docker images to $(DOCKER_REGISTRY)/$(DOCKER_REPO)...$(NC)"
	@echo "$(YELLOW)Pushing version: $(VERSION)$(NC)"
	@docker push $(DOCKER_REGISTRY)/$(DOCKER_REPO):$(VERSION)
	@docker push $(DOCKER_REGISTRY)/$(DOCKER_REPO):latest
	@echo "$(GREEN)Docker images pushed successfully!$(NC)"
	@echo "$(YELLOW)Pull commands:$(NC)"
	@echo "  docker pull $(DOCKER_REGISTRY)/$(DOCKER_REPO):$(VERSION)"
	@echo "  docker pull $(DOCKER_REGISTRY)/$(DOCKER_REPO):latest"

docker-release: ## Build, tag and push Docker image for release
	@echo "$(BLUE)Creating Docker release...$(NC)"
	@if [ -z "$(DOCKER_REGISTRY)" ]; then \
		echo "$(RED)Error: DOCKER_REGISTRY not set$(NC)"; \
		echo "$(YELLOW)Usage: make docker-release DOCKER_REGISTRY=your-registry.com [DOCKER_REPO=custom-name] [VERSION=1.0.0]$(NC)"; \
		exit 1; \
	fi
	@echo "$(YELLOW)Release Information:$(NC)"
	@echo "  Registry: $(DOCKER_REGISTRY)"
	@echo "  Repository: $(DOCKER_REPO)"
	@echo "  Version: $(VERSION)"
	@echo "  Git Commit: $(GIT_COMMIT)"
	@echo "  Git Branch: $(GIT_BRANCH)"
	@echo "  Build Date: $(BUILD_DATE)"
	@echo ""
	@read -p "Continue with release? (y/N): " confirm && [ "$confirm" = "y" ] || exit 1
	@$(MAKE) docker-push DOCKER_REGISTRY=$(DOCKER_REGISTRY) DOCKER_REPO=$(DOCKER_REPO) VERSION=$(VERSION)
	@echo "$(GREEN)🚀 Release $(VERSION) completed successfully!$(NC)"

docker-run: ## Run Docker container
	@echo "$(BLUE)Running Docker container...$(NC)"
	@docker-compose up -d
	@echo "$(GREEN)Docker container started$(NC)"

docker-stop: ## Stop Docker container
	@echo "$(BLUE)Stopping Docker container...$(NC)"
	@docker-compose down
	@echo "$(GREEN)Docker container stopped$(NC)"

docker-logs: ## Show Docker logs
	@docker-compose logs -f

docker-shell: ## Open shell in Docker container
	@docker-compose exec libreoffice-converter /bin/bash

docker-clean: ## Clean up Docker images and containers
	@echo "$(BLUE)Cleaning up Docker resources...$(NC)"
	@docker-compose down --volumes --remove-orphans
	@docker system prune -f
	@echo "$(GREEN)Docker cleanup completed$(NC)"

# Utility
version: ## Show version information
	@echo "$(BLUE)Version Information:$(NC)"
	@echo "  App Name: $(APP_NAME)"
	@echo "  Version: $(VERSION)"
	@echo "  Git Commit: $(GIT_COMMIT)"
	@echo "  Git Branch: $(GIT_BRANCH)" 
	@echo "  Build Date: $(BUILD_DATE)"
	@echo "  Python Version: $(PYTHON_VERSION)"

clean: ## Clean up temporary files and caches
	@echo "$(BLUE)Cleaning up...$(NC)"
	@rm -rf __pycache__/
	@rm -rf .pytest_cache/
	@rm -rf .coverage
	@rm -rf htmlcov/
	@rm -rf dist/
	@rm -rf build/
	@rm -rf *.egg-info/
	@rm -rf temp/*
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -delete
	@echo "$(GREEN)Cleanup completed$(NC)"

logs: ## Show application logs
	@tail -f logs/*.log 2>/dev/null || echo "No log files found"

health: ## Check application health
	@echo "$(BLUE)Checking application health...$(NC)"
	@curl -f http://localhost:8000/health || echo "$(RED)Application not responding$(NC)"

check-deps: ## Check for dependency updates
	@echo "$(BLUE)Checking for dependency updates...$(NC)"
	@pip list --outdated

# Documentation
docs: ## Generate documentation
	@echo "$(BLUE)Generating documentation...$(NC)"
	@mkdir -p docs
	@echo "Documentation generation not implemented yet"

# Release
dist: ## Build distribution packages
	@echo "$(BLUE)Building distribution packages...$(NC)"
	@$(PYTHON) setup.py sdist bdist_wheel

# All-in-one commands
install-all: venv install install-dev ## Create venv and install all dependencies
	@echo "$(GREEN)All dependencies installed$(NC)"

check-all: lint type-check test ## Run all checks
	@echo "$(GREEN)All checks completed$(NC)"

# Quick development setup
quick-start: install-dev test-quick run ## Quick development setup and start

# Production deployment
deploy: docker-build docker-run ## Build and deploy with Docker
	@echo "$(GREEN)Deployment completed$(NC)"

# Release workflow
release: check-all docker-release ## Complete release workflow
	@echo "$(GREEN)🎉 Release workflow completed!$(NC)"

# Status check
status: ## Show project status
	@echo "$(BLUE)Project Status:$(NC)"
	@echo "Python version: $(python3 --version)"
	@echo "Python location: $(which python3)"
	@echo "Pip version: $(pip --version)"
	@echo "LibreOffice: $(libreoffice --version 2>/dev/null || echo 'Not installed')"
	@echo "Docker: $(docker --version 2>/dev/null || echo 'Not installed')"
	@echo "Virtual env: $([ -d $(VENV) ] && echo 'Present' || echo 'Not created')"
	@echo "Python compatibility: $(python3 -c 'import sys; print("✅ Compatible" if sys.version_info >= (3,11) else "❌ Requires Python 3.11+")')"