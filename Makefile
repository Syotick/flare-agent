# Flare Agent 本地开发命令（Git Bash / macOS / Linux）
# 环境约定：conda env flare-agent（Python 3.12，与 CI 一致）；不使用 .venv
CONDA_ENV ?= flare-agent
PY := conda run -n $(CONDA_ENV) python
PYTHONPATH := services

.PHONY: setup install dev test lint fmt clean web web-install web-dev web-build

setup: ## 首次：创建 conda 环境并安装依赖
	conda create -n $(CONDA_ENV) python=3.12 -y
	$(PY) -m pip install -U pip
	$(PY) -m pip install -r requirements-dev.txt
	$(PY) -m pip install -e .   # 可编辑安装：让 importlib.metadata 读到版本等元数据

install: ## 环境已存在：仅安装/更新依赖
	$(PY) -m pip install -U pip
	$(PY) -m pip install -r requirements-dev.txt
	$(PY) -m pip install -e .

dev: ## 启动 Agent Runtime（热重载，端口 8000）
	PYTHONPATH=services $(PY) -m uvicorn agent_runtime.main:app --reload --port 8000

test: ## 运行单元测试
	PYTHONPATH=services $(PY) -m pytest tests -q

lint: ## Ruff + Black 检查
	$(PY) -m ruff check services tests
	$(PY) -m black --check --line-length 100 services tests

fmt: ## 自动格式化
	$(PY) -m black --line-length 100 services tests
	$(PY) -m ruff check --fix services tests

web-install: ## Web：安装依赖
	cd services/web && npm install

web-dev: ## Web：Vite dev 服务器（5173，/v1 代理到 8000）
	cd services/web && npm run dev

web-build: ## Web：生产构建（输出 services/web/dist，供 app.py 静态托管）
	cd services/web && npm run build

web: web-dev ## Web：默认走 dev 模式

clean: ## 删除环境
	conda env remove -n $(CONDA_ENV) -y
