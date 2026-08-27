# Flare Agent · 模块级技术设计（M1 核心交付）

> 版本：v0.1 ｜ 日期：2026-08-27 ｜ 状态：draft（随 M1 评审定稿）
> 上游：01-architecture-overview.md、docs/product/requirements/01-development-requirements.md
> 关联 ADR：0001-0014；本设计新增决策见 0015

---

## 1. 目标与范围

- 把架构总览落到**模块级**：目录结构、服务职责、关键 API、数据模型、Agent 图、本地开发环境。
- 为 M2 开发提供可直接落地的蓝图；M5 再上云与压测。

## 2. 仓库结构（Monorepo）

```
flare-agent/
├── docs/                        # 文档中心（见 docs/README.md）
├── services/                    # 后端服务（模块化单体起步，按需拆分）
│   ├── agent_runtime/          # Agent 编排运行时（FastAPI + LangGraph）
│   ├── model_gateway/          # 模型网关（OpenAI 兼容：路由/缓存/配额）
│   ├── rag/                    # RAG：入库管线 + 检索服务
│   ├── tools_gateway/          # 工具/MCP 网关 + ToolRegistry
│   ├── sandbox/                # 沙箱执行服务（Docker dev / Kata prod）
│   ├── web/                    # Web 控制台（Vite + React，Node 工程）
│   └── common/                 # 共享：schemas、SDK、logging、OTel、配置
├── infra/
│   ├── docker-compose.yml       # 本地环境一键起（PG/Redis/Milvus|Qdrant/MinIO/...）
│   ├── k8s/                     # 阿里云 ACK 部署（Helm，M5）
│   └── scripts/                 # 运维脚本
├── eval/                        # 评测：golden set + RAGAS + 任务成功率
├── tests/                       # 契约/端到端测试
└── .github/workflows/           # CI/CD（已配置）
```

> 起步为**模块化单体**（一个仓库一个 Python 工程，services/ 内为可独立启动的 app + 共享 common），
> 压测/流量上去后再按服务拆分部署（ADR-0015）。

## 3. 服务职责与交互

```
Web ──▶ agent-runtime ──▶ model-gateway ──▶ 模型供应商/自托管 vLLM
  │         │  │                 ▲
  │         │  └──▶ tools-gateway ──▶ MCP Server / 内置工具
  │         │         │
  │         ▼         └──▶ sandbox（执行）
  │      rag（检索/入库）
  │         │
  └─────────┴──▶ PG / Redis / Milvus / MinIO
```

| 服务 | 职责 | 关键依赖 |
| --- | --- | --- |
| agent-runtime | 会话/任务管理、LangGraph 编排、审批(interrupt)、流式、上下文/记忆 | PG、Redis、LangGraph |
| model-gateway | OpenAI 兼容 API、多供应商路由、语义缓存、配额成本、重试降级 | Redis |
| rag | 文档解析/分块/嵌入/入库（异步）、混合检索+重排、溯源 | MinIO/OSS、Milvus、MQ |
| tools-gateway | 工具注册、MCP 客户端适配、鉴权/限流/审计、敏感操作审批触发 | Redis |
| sandbox | 代码/命令执行（强隔离）、资源限额、产物上传 | MinIO/OSS、容器/微VM |
| web | 任务创建/实时流/审批/历史/管理台 | — |

## 4. 关键 API 设计（OpenAI 兼容 + 业务 REST）

### 4.1 任务与流式
- `POST /v1/tasks` — 创建任务 `{project_id, prompt, mode: agent|workflow, budget}` → `{task_id}`
- `GET /v1/tasks/{id}` — 任务状态/结果
- `GET /v1/tasks/{id}/stream` — SSE 事件流（token/工具调用/审批请求/完成）
- `POST /v1/tasks/{id}/cancel` — 取消（省 token）
- `POST /v1/tasks/{id}/approvals/{approval_id}` — 审批 `{decision: approve|reject}`

### 4.2 模型网关（OpenAI 兼容）
- `POST /v1/chat/completions`（含 stream）+ `/v1/models`
- 认证：租户级 API Key；响应带 `x-flare-usage`（成本/配额）

### 4.3 知识库（RAG）
- `POST /v1/kb/documents` — 上传文档（异步入库）
- `GET /v1/kb/documents/{id}` — 入库状态
- `POST /v1/kb/search` — `{query, top_k, filters}` → 命中+引用

### 4.4 管理
- `/admin/tenants`、`/admin/quotas`、`/admin/usage`、`/admin/audit`

> 统一错误码、分页、幂等键（Idempotency-Key）、trace_id 贯穿（OTel）。

## 5. 数据模型（PostgreSQL 核心表）

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| tenants | id, name, plan, status | 租户 |
| users | id, tenant_id, email, role | 用户（SSO 预留） |
| sessions | id, tenant_id, user_id, project_id | 会话 |
| tasks | id, session_id, status, budget, started_at, finished_at, error | 任务（状态机） |
| messages | id, task_id, role, content, token_count, ts | 对话/轨迹 |
| tool_calls | id, task_id, tool, params, result, duration_ms, risk | 工具调用（审计） |
| approvals | id, task_id, action, status, decided_by, decided_at | 审批 |
| kb_documents | id, tenant_id, name, status, version, object_key(OSS) | 文档（版本化） |
| kb_chunks_meta | id, doc_id, chunk_index, vector_id, source_page, hash | 分块元数据（向量在 Milvus） |
| audit_logs | id, tenant_id, actor, action, target, ip, ts | 不可变审计 |
| usage_records | id, tenant_id, user_id, model, tokens, cost, ts | 成本计量 |

> 会话热数据在 Redis（短期记忆），冷数据落 PG；checkpoint 用 LangGraph PostgresSaver 存 `checkpoints` 表。

## 6. LangGraph Agent 图设计

```
            ┌────────────┐
 start ──▶  │ planner    │ 拆解目标/预算
            └─────┬──────┘
                  ▼
            ┌────────────┐     需要检索? ──▶ rag_search
            │  actor     │   ── 选工具? ──▶ tool_executor ──▶ sandbox
            │  (模型)    │   ── 敏感动作?─▶ human_approval(interrupt) ──▶ actor
            └─────┬──────┘   ── 记忆? ────▶ memory_rw
                  ▼
            ┌────────────┐   自检失败 ─▶ 回 actor
            │  reflect    │
            └─────┬──────┘
                  ▼
             finalize ──▶ 交付（结果/产物/PR）
```

- 持久化：LangGraph PostgresSaver 全程 checkpoint（进程重启可恢复）。
- 预算熔断：步数/成本/时长任一超限 → 中断并通知（防死循环）。
- 人工审批：`interrupt` 节点 + approvals 表 + Web 审批按钮。

## 7. 本地开发环境（docker-compose）

| 组件 | 镜像 | 用途 |
| --- | --- | --- |
| postgres | postgres:16 | 主库（含 pgvector 扩展备用） |
| redis | redis:7 | 缓存/会话/限流 |
| milvus | milvusdb/milvus | 向量库（本地可换 qdrant 降级） |
| minio | minio/minio | 对象存储模拟 OSS |
| agent-runtime / model-gateway / rag / web | 本地构建 | 服务 |
| （可选）rocketmq | apache/rocketmq | 消息队列（默认本地用 Redis Streams 降级） |

> `make dev` / `docker compose up` 一键起；环境变量走 `.env`（模板 `.env.example`）。

## 8. 演进路径

1. **M2-M3**：模块化单体 + 本地 docker-compose，单进程跑全部服务（开发效率优先）。
2. **M4-M5**：按服务拆分部署（agent-runtime/model-gateway/rag 独立扩缩），接 MQ 解耦长任务。
3. **M5+**：ACK 多可用区 + HPA + 金丝雀 + 压测验证。

## 9. 与 ADR 对应

- 单体优先/Monorepo → ADR-0015（本设计新增）
- 其余选型 → ADR-0001~0014
