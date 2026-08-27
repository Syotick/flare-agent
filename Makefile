# Flare Agent 本地开发命令（Git Bash / macOS / Linux）
PYTHON ?= python
PYTHONPATH := services

.PHONY: install dev test lint fmt clean

install: ## 创建虚拟环境并安装依赖
	$(PYTHON) -m venv .venv
	.venv/bin/python -m pip install -U pip
	.venv/bin/python -m pip install -r requirements-dev.txt

dev: ## 启动 Agent Runtime（热重载，端口 8000）
	PYTHONPATH=services .venv/bin/uvicorn agent_runtime.main:app --reload --port 8000

test: ## 运行单元测试
	PYTHONPATH=services .venv/bin/pytest tests -q

lint: ## Ruff + Black 检查
	.venv/bin/ruff check services tests
	.venv/bin/black --check --line-length 100 services tests

fmt: ## 自动格式化
	.venv/bin/black --line-length 100 services tests
	.venv/bin/ruff check --fix services tests

clean: ## 清理产物
	rm -rf .venv .pytest_cache .ruff_cache .mypy_cache htmlcov services/**/__pycache__
