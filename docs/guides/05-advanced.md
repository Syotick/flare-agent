# 05 · 进阶主题

> 目标读者：要把 Flare Agent 用深、用对的人。
> 读完本篇你会：**掌握模型/权限/工作区/RAG/记忆/多 Agent/MCP/技能/运维的配置与最佳实践**。

---

## 1. 模型配置（再深一点）

### Provider 三种

| provider | 协议 | 适用 |
| --- | --- | --- |
| `mock` | 内置 | 开发联调、测试、无 Key 跑通 |
| `openai` | OpenAI 兼容 | DeepSeek / 通义百炼 / SiliconFlow / vLLM / Ollama… |
| `anthropic` | Claude Messages 原生 | Claude |

### 优先级（重要）

真实环境变量 **>** 控制台保存的 `data/model_config.json` **>** `.env`。生产用 env/K8s Secret 覆盖即可压制 UI 配置。

### per-task 模型选择

前端 Composer 第二个 chip 选的模型，会作为 `model` 字段随任务提交。后端按自定义供应商 profile 构建独立 provider 跑该任务；profile 不存在 / 配错 → **自动回退默认模型**（不会失败）。

### 重试策略

模型网关内置瞬态重试：网络错误、超时、429/5xx 指数退避（最大 4 次）；**流式**只在连接建立失败时重试（中途断了不重试，保证流式连贯）。

## 2. 权限与审批策略

### 审批级别

| 配置 | 含义 |
| --- | --- |
| `FLARE_APPROVAL_REQUIRE_LEVEL=destructive`（默认） | 破坏性工具（bash）需审批；写文件不用（write<destructive） |
| `FLARE_APPROVAL_REQUIRE_LEVEL=write` | 写文件 + 跑命令都要审批（更严） |
| `FLARE_APPROVAL_REQUIRE_LEVEL=read` | 所有非只读都审批 |

### TOFU（首用信任）

同一作用域（默认会话线程 `thread`）内，某工具**获批过一次后自动放行**，避免每个文件都问一次。
- `FLARE_APPROVAL_TOFU=true/false` 开关
- `FLARE_APPROVAL_TOFU_SCOPE=thread|tenant|off`：`thread` 按会话、`tenant` 按租户、`off` 关闭

### 审批后端

- `local`：进程内（默认，单实例）
- `redis`：多实例共享，跨节点决策轮询唤醒（生产多副本用）

### 权限模式（会话级，Composer 第一个 chip）

只读 = 连写的能力都没有（工具不注入）；无限制 = 免审批。详见[核心概念](02-core-concepts.md#7-权限模式permission-mode--整会话的松紧度)。

## 3. 工作区代码能力（Agent 干活的边界）

### 六工具与安全设计

| 工具 | 安全行为 |
| --- | --- |
| `write` | 覆盖已存在文件前**必须先 read**；目标在工作区外 → 拒绝 |
| `edit` | 必须**先 read**；文件自 read 后变化（size+mtime）→ 拒绝，防覆盖别人改的东西 |
| `bash` | 每次全新 Git Bash 子进程（无状态残留）；默认 30s 超时（上限 120s）；输出 64KB 截断；`NO_COLOR` 等环境清理 |
| `read/glob/grep` | 只读；glob≤100 条、grep≤250 条；自动跳过 `.git/node_modules` 等目录和二进制 |

### 绝对路径

只读工具允许绝对路径（读系统文件/日志）；`write/edit` 只允许工作区内（越界拒绝）。`bash` 的 cwd 默认是工作区。

## 4. RAG 知识库

### 流程

入库（按标题分块、向量化）→ 混合检索（向量 + BM25 + RRF 融合）→ Rerank → 带溯源引用给模型。

### 用起来

控制台 **知识库** 页：输入标题 + 正文/文档 → 入库；然后对话里 Agent 自动检索。API：

```bash
# 入库
curl -X POST http://127.0.0.1:8000/v1/kb/documents \
  -H 'Content-Type: application/json' \
  -d '{"title":"产品手册","content":"..."}'

# 检索
curl 'http://127.0.0.1:8000/v1/kb/search?query=怎么部署&top_k=3'
```

### 评测

内置评测（含 RAGAS 指标）：`pytest tests/unit/test_rag_eval.py`，用数据集对比不同检索策略（BM25 / 向量 / RRF 融合）。

## 5. 分层记忆

三层自动注入：**长期事实**（用户/项目属性）+ **向量记忆**（相关历史片段）+ **会话近期上下文**（同线程最近 6 轮）。

- 控制台 **记忆** 页可查看 / 管理
- 记忆通过 `mem_tools`（`mem_set` / `mem_search` 等）让 Agent 主动读写
- 任务开始自动召回相关记忆注入上下文

## 6. 多 Agent（subagent）

任务内可派生子任务：主 Agent 觉得某步可以独立干时，用 subagent 工具交出去，子任务共享模型与工具注册表，结果回收。适合：并行调研、长任务拆解。

```bash
# 能力页可查看当前注册的工具/技能/Agent 能力
curl http://127.0.0.1:8000/v1/capabilities
```

## 7. MCP 网关

任意 MCP 服务器即插即用。配置在环境变量（JSON）或控制台：

```bash
FLARE_MCP_SERVERS='[{"name":"filesys","url":"http://localhost:9001/mcp","transport":"streamable_http","headers":{},"enabled":true}]'
```

配置的 MCP 工具会自动进 ToolRegistry，Agent 就能调用外部 MCP 能力。

## 8. 技能包（Skills）

技能 = 一个带 `SKILL.md`（声明式：名称/描述/用法）的目录，放到 `data/skills/`。Agent 遇到匹配任务会自动读技能并用起来；控制台 **能力** 页可查看已加载技能。

## 9. OpenAI 兼容 API

用任何 OpenAI SDK 直接调，把 Flare 当"多工具 Agent 后端"：

```python
import openai
client = openai.OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="unused")
resp = client.chat.completions.create(model="flare", messages=[{"role":"user","content":"hi"}])
```

生产可设 `FLARE_API_KEY` 启用认证。

## 10. 运维

- **指标**：`GET /metrics`（Prometheus 文本格式）——任务成功率、端到端耗时、错误预算等
- **SLO**：`FLARE_SLO_AVAILABILITY`（默认 0.99）、`FLARE_SLO_P95_LATENCY_SECONDS`（默认 5s）、`FLARE_SLO_PERIOD_DAYS`（30 天）；控制台 **运维** 页看错误预算
- **日志**：结构化日志，`FLARE_LOG_LEVEL` 调级别
- **OTel**：`FLARE_OTEL_ENDPOINT` 配置导出端点（空 = 不启用）
- **健康**：`GET /health`

### 生产 checklist（本地 → 生产）

1. 配真实模型 + API Key（环境变量，不用 UI）
2. `FLARE_ENV=prod` + `FLARE_API_KEY` 启用 API 认证
3. 任务存储换 `redis`（多实例）；审批后端 `redis`
4. 数据目录 `data/` 挂持久卷（SQLite 文件 + skills）
5. 前置反向代理（TLS）、看 /metrics 建告警
6. 沙箱：当前本地子进程足够单机；多租户/强隔离再看容器沙箱（规划中）

---

## 更多

- 产品与技术决策背景：ADR（[docs/adr](../adr)）、架构评审（[docs/product/architecture](../product/architecture)）
- 项目记忆与进度：[CLAUDE.md](../../CLAUDE.md)
- 工程规范：[docs/engineering](../engineering)

回到 [docs 总索引](../README.md)。