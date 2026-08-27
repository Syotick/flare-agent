# Flare Agent · 生产部署指南（阿里云 · 实践 + 真理）

> 版本：v1.0 ｜ 日期：2026-08-27 ｜ 状态：draft
> 定位：从"能跑"到"能上线"。镜像、ACK、OSS、PG、Redis、OTel、多租户、容量、SLO、回滚。
> 标注：✅ = 已实现；⏳ = M5/M6 路线图（按 plan 落地）。
> 前置：先读 [04-advanced-development-guide](./04-advanced-development-guide.md) 的开发→生产切换矩阵。

---

## 1. 生产部署架构（先看全景）

- 真理：生产 = 无状态应用 + 有状态底座 + 可观测 + 可回滚。App 副本越多越好扩，状态越集中越好管；
  应用层绝不本地落盘（磁盘没了 = 数据没了）。
- 目标拓扑（阿里云）：

    用户 ── HTTPS ──> ALB / Nginx Ingress ──> ACK (K8s) 多副本 flare-agent
                                              ├─> 云数据库 PG（pgvector：kb_chunks / memory_chunks / facts / checkpoint）
                                              ├─> 云 Redis（任务存储 / 事件队列 / 缓存，M5）
                                              ├─> OSS（原始文档 / 多模态 / 日志归档）
                                              └─> OTel Collector ──> SLS（日志）+ ARMS（链路）+ Prometheus/云监控（指标）

- 阿里云组件映射：ALB（7 层）+ ACK（K8s）+ RDS PG（pgvector 扩展或自建 PG）+ 云 Redis + OSS +
  ARMS（应用监控/链路）+ SLS（日志）+ 云监控（指标/告警）。
- 现状：infra/docker-compose.yml 已备好 PG(pgvector)/Redis/MinIO(OSS 模拟)/Qdrant ✅；
  Dockerfile、K8s manifests、OTel 导出为 M5 ⏳。

## 2. 镜像构建（Dockerfile 示例，M5 提交到 infra/）

- 真理：镜像 = 最小 + 可复现 + 非 root + 多阶段。先装依赖（层缓存）再 COPY 代码；健康检查必须有。
- 注意：开发机用 conda（Python 3.12），镜像用官方 slim 镜像即可——别把 conda 带进镜像。

    FROM python:3.12-slim AS base
    WORKDIR /app
    ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
    COPY pyproject.toml requirements.txt ./
    RUN pip install --no-cache-dir -r requirements.txt && pip install -e .
    COPY services ./services
    COPY --chown=1000:1000 . ./  # 更严格时只 COPY 需要的目录
    USER 1000
    EXPOSE 8000
    HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
    CMD ["uvicorn", "agent_runtime.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

- .dockerignore 至少排除：data/ .git/ .pytest_cache/ .ruff_cache/ node_modules/（构建产物）。
- 上线前必查（踩坑实录）：`pip install -e .` 后 `python -c "import memory"` 必须成功——
  pyproject packages.find 漏过 memory* 时开发（PYTHONPATH）正常、镜像装上就挂。已修复并回归。

## 3. 配置与密钥（12-factor）

- 真理：配置全部来自环境变量（前缀 FLARE_），密钥进 Secret 不进镜像；config.py 的 extra="forbid"
  保证拼错变量名在启动即报错（fail-fast），绝不静默沿用默认值。
- 生产必设：FLARE_ENV=prod、FLARE_DATABASE_URL、FLARE_REDIS_URL、FLARE_OBJECT_STORE_*、
  FLARE_MODEL_PROVIDER/FLARE_MODEL_API_KEY、FLARE_CORS_ORIGINS（JSON 白名单，勿用 *）。
- K8s 做法：ConfigMap 放非敏感配置，Secret 放 API Key/DB 密码；本地用 .env（不入库，.gitignore 已配）。

## 4. 存储演进（关键：怎么从 SQLite 迁到云底座）

- 真理：因为所有存储都走协议/工厂，迁移 = 换实现 + 跑通全量测试，不是重写上层。
- 迁移清单（M5）：
  - kb/memory 向量：SqliteVectorStore → PgVectorStore——同一 VectorStore 协议；
    **同一 PG 实例、分表**（kb_chunks / memory_chunks，schema 相同：doc_id/chunk_index/text/vector）；
  - facts 事实表：SQLite → PG 同结构（project_id/key/value/updated_at，PK(project_id,key)）；
  - checkpointer：SQLite → AsyncPostgresSaver（checkpoint.py 生产分支已实现，非 dev fail-fast）；
  - 任务/事件：进程内 dict → SqliteTaskStore/RedisTaskStore（task_store.py 已实现，memory|sqlite|redis 三档）；
  - 原始文档/多模态：OSS（FLARE_OBJECT_STORE_* 已预留，docker-compose 用 MinIO 模拟）。
- 迁移纪律：先双写对账、再灰度切换、数据校验脚本验证 chunk 数与检索一致性；切完保留旧库 7 天兜底。

### 4.1 M5 代码层交付（已就绪，待服务器部署）

> 服务器到位后：docker build -f infra/Dockerfile → 推 ACR → kubectl apply -f infra/k8s/。以下代码全部本地可测。

- infra/Dockerfile + .dockerignore：多副本运行时镜像（requirements + 包 + OTel/asyncpg/redis 生产依赖）；
- infra/k8s/：01-configmap → 02-secret（占位，生产用 ExternalSecrets/KMS）→ 03-deployment（双副本+探针+资源）
  → 04-service → 05-hpa（CPU70%，2~10 副本）→ 06-ingress → 07-otel-collector（OTLP→ARMS 占位）；
- 多租户：X-Tenant-Id 头 → TenantMiddleware → contextvar；任务带 tenant_id（路由默认读取）；
- OTel：flare_common/otel.py，FLARE_OTEL_ENDPOINT 为空则 no-op、有端点且缺 SDK 则 fail-fast；
- PgVectorStore（rag/pgstore.py）：同协议实现，pgvector HNSW 索引 + 余弦检索，连不上 PG 503；
- 双写对账：scripts/reconcile.py --src <sqlite> --dst <pg dsn> [--fix]，缺什么补什么、差异可审计。

## 5. 可观测性（OTel：logs / traces / metrics）

- 真理：上线 ≠ 能用。看不到链路就不算可运维；日志要结构化、请求要有 trace_id、指标要有基线。
- 三信号落地（阿里云）：
  - 日志：结构化 JSON 日志 → SLS（已有 flare_common.logging 结构化 ✅）；
  - 链路：Agent 轮次/工具/LLM 调用的 trace → ARMS（flare_common/otel.py ✅：FLARE_OTEL_ENDPOINT 指向 Collector/ARMS，空则 no-op）；
  - 链路：请求 → Agent 轮次 → 工具调用 → LLM 调用的 trace → ARMS/OTel Collector；
  - 指标：QPS / P99 / 错误率 / 工具失败率 / 并发任务数 / 检索耗时 / LLM 调用数与配额余量 → Prometheus + 云监控。
- 关键告警指标基线（示例）：P95 首 token < 1s、任务完成率 > 99.5%、LLM API 配额余量 < 20% 告警。

## 6. 多租户与安全

- 真理：多租户 = 数据隔离 + 配额 + 审计。project_id 隔离已有 ✅；tenant_id 维度已代码就绪 ✅
  （X-Tenant-Id → contextvar → 任务/审计带租户；DB 分表随 PG 迁移落地）。
- 安全清单：CORS 白名单（勿 *）、请求限流（按 tenant/IP）、敏感信息脱敏（日志里不打印 API Key/事实值全文）、
  Secret 托管、全链路 HTTPS（ALB 终结）、依赖漏洞扫描（CI 里 pip-audit 级别）。

## 7. 并发与容量（百万级目标）

- 真理：并发 100 万不是"一台机器很能扛"，而是**无状态水平扩展**：每副本 QPS x 副本数 >= 峰值，
  且留 50% 余量；状态全在底座（PG/Redis），副本随意增删。
- 容量模型：
  - 模型调用是主要延迟 → 按任务预算（max_steps）控制轮次、结果缓存、并发任务数限流；
  - LLM API 配额要提前算：并发任务数 x 平均轮次 x 峰值时长 = 每分钟调用数，超配额会 429（flare_common 有 RateLimitError）；
  - 检索耗时：pgvector HNSW 索引 + 混合检索（M3c）压 p95；
  - 压测按 engineering/02-load-testing-plan.md 执行，M5 用真实底座跑出基线再定副本数。
- 瓶颈优先级：模型网关 > PG 连接池 > Redis 吞吐；用连接池（如 asyncpg 池）+ Redis 分片提前解掉。

## 8. SLO / 告警 / 回滚（M6）

- 真理：SLO 是团队对外的承诺，error budget 决定是否允许发版（可用性 99.9% ≈ 每年 8.76 小时不可用）。
- 示例 SLO：可用性 99.9%、P95 首 token < 1s、P95 任务完成 < 30s、任务完成率 > 99.5%。
- 告警分级：P0（服务不可用/数据丢失）立即人肉；P1（P95 恶化）15 分钟响应；P2（容量/配额预警）工作日处理。
- 回滚策略：镜像版本回退（多副本滚动更新）+ DB 迁移前备份 + 金丝雀（先 10% 流量）。

## 9. 上线检查清单

- [x] wheel 安装后 `import memory` 通过（pyproject 含 memory*）
- [x] FLARE_ENV=prod 启动无静默降级（fail-fast 生效；checkpoint/向量/任务存储三处均有 503 守卫）
- [ ] PG（pgvector）/ Redis / OSS 连通且 scripts/reconcile.py 对账通过
- [x] OTel 导出代码就绪（FLARE_OTEL_ENDPOINT 生效，空则 no-op）；待上报 SLS/ARMS/Prometheus
- [ ] /health 探针通过，多副本滚动更新演练 OK
- [ ] CORS 白名单 / HTTPS / Secret 就位，无明文密钥
- [ ] 压测达到 SLO 基线（含 50% 余量）
- [ ] 回滚演练通过（镜像回退 + DB 备份恢复）

## 10. 下一步（M5/M6 路线）

- **M5 云原生上线**：✅ 代码层全部就绪（infra/Dockerfile + infra/k8s/ + OTel 导出 + 多租户 tenant_id +
  Redis/SQLite 任务存储 + PgVectorStore + AsyncPostgresSaver + scripts/reconcile.py 双写对账，103 测试全绿）；
  ⏳ 剩真上云动作（买服务器 → docker build 推 ACR → kubectl apply → 对账/压测）。
- **M6 生产运营**：SLO/error budget 落地、告警分级值班、容量压测与扩缩容策略、季度演练。
- 建议：M3c（RAG 评测/混合检索/重排）先做——把检索质量量化，上线前才有"多好"的基线。
