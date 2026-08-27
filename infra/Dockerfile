# syntax=docker/dockerfile:1
# Flare Agent 运行时镜像（M5 云原生）
# 本地验证：docker build -f infra/Dockerfile -t flare-agent:local .
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/services \
    FLARE_ENV=prod
WORKDIR /app
COPY pyproject.toml requirements.txt README.md ./
COPY services ./services
COPY scripts ./scripts
# 依赖 + 包安装 + M5 生产附加依赖（OTel/asyncpg/redis）
RUN pip install -r requirements.txt && \
    pip install . && \
    pip install --no-cache-dir opentelemetry-sdk opentelemetry-exporter-otlp-proto-http asyncpg redis
EXPOSE 8000
# 生产：多副本 + FLARE_TASK_STORE=redis；单副本可 sqlite
CMD ["uvicorn", "agent_runtime.main:app", "--host", "0.0.0.0", "--port", "8000"]
