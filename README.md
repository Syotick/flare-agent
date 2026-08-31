# Flare Agent · 本地优先的 AI Agent 平台

> **让 AI 真的能读代码、写代码、跑命令、查资料、干活的 Agent 平台。**
> FastAPI + LangGraph 后端 · React 前端 · 开箱即用，5 分钟跑通。

[![CI](https://github.com/Syotick/flare-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Syotick/flare-agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.12-blue)
![Tests](https://img.shields.io/badge/tests-265%20passing-brightgreen)

Flare Agent 是一个**本地优先**的 Agent 执行平台：你给它一个工作区目录，它就能在里面**读代码、写代码、搜索、跑命令**，一步步完成你的任务——过程实时可见、每步可审批、权限可控。

对标 DeepSeek Harness / Claude Code 的交互形态，但**自托管、可二次开发、Web 控制台**：后端一个进程 + 前端一个 build 就是完整产品。

---

## ✨ 特性（都是真实现，不是规划）

### Agent 执行
- **任务即会话**：发一个任务，后台用 LangGraph 编排执行，**SSE 实时流**回推每一步（打字机式回复 + 工具调用轨迹）
- **工作区 = 真实目录**：选一个服务器目录当工作区，Agent 拥有 `read / write / edit / glob / grep / bash` 六种工具，真正能动手干活（对标 DSH）
- **读前置保护**：覆盖已存在文件前必须先读；`edit` 带版本校验（size+mtime），防盲目覆盖
- **越界拒绝**：`write / edit` 目标在工作区外直接拒绝（OUT_OF_BOUNDS），`bash` 走审批兜底

### 安全与权限
- **三种权限模式**（会话级）：🔒 只读（只注入只读工具，写能力物理不存在）· 🛡 批准（写文件/跑命令逐次审批）· ⚡ 无限制（自动执行）
- **审批门 + TOFU**：破坏性工具默认需人工审批；同一会话内批准过一次的工具后续自动放行（防审批疲劳）
- **工具权限分级**：`read < write < destructive`，审批策略可配（`FLARE_APPROVAL_REQUIRE_LEVEL`）

### 模型
- **多供应商网关**：`mock`（零配置联调）/ `openai` 兼容（DeepSeek / 通义百炼 / SiliconFlow / vLLM / Ollama…）/ `anthropic`（Claude 原生）
- **会话级模型选择**：每个任务可指定自定义模型 profile，配错自动回退默认模型
- **瞬态重试**：网络/超时/5xx 指数退避，流式只在连接失败时重试

### 记忆与知识
- **RAG 知识库**：入库 → 混合检索（向量 + BM25 + RRF）→ Rerank → 带溯源引用，含 RAGAS 评测
- **分层记忆**：长期事实 + 向量记忆 + 会话近期上下文，任务开始自动召回注入

### 扩展与集成
- **MCP 网关**：任意 MCP 服务器即插即用（流式 HTTP）
- **技能包（Skills）**：声明式技能（`SKILL.md`），可安装到 `data/skills`
- **多 Agent**：任务内可派生子任务（subagent），共享模型与工具注册表
- **OpenAI 兼容 API**：任何 OpenAI SDK / curl 直接调 `/v1/chat/completions`
- **CLI**：`flare` 命令，终端里发任务

### 工程
- **可观测**：`/metrics` Prometheus 指标 + SLO 错误预算页面 + OTel 埋点（可关）
- **持久化**：任务 / 知识库 / 记忆全部落 SQLite（`data/`），重启不丢，`redis` 可切换
- **265 个测试**：单元 + API + 工作区工具全链路，`pytest` 一键跑

---

## 🚀 快速开始（本地 5 分钟）

> 前置：Python 3.12、Node 18+。Windows 需要 Git Bash（Agent 跑命令用）。

```bash
# 1. 装 Python 依赖（建议虚拟环境）
pip install -r requirements.txt

# 2. 装前端依赖并构建（构建后由后端直接挂载，无需再开 dev server）
cd services/web && npm install && npm run build && cd ../..

# 3. 启动后端
python -m uvicorn agent_runtime.main:app --host 127.0.0.1 --port 8000
```

打开 **http://127.0.0.1:8000** —— 这就是完整控制台。

**发第一个任务**（此时模型是 mock，Agent 用预置逻辑走完流程）：

```bash
curl -X POST http://127.0.0.1:8000/v1/tasks \
  -H 'Content-Type: application/json' \
  -d '{"task_input":"你好，帮我打个招呼"}'
```

拿返回的 `task_id` 看实时流：

```bash
curl -N http://127.0.0.1:8000/v1/tasks/<task_id>/stream
```

### 接入真实模型（30 秒）

在控制台左侧 **模型** 页填 Provider / Base URL / Model Name / API Key（内置 DeepSeek、通义百炼、SiliconFlow、Ollama 等预设），保存即热生效。或写 `.env`：

```bash
FLARE_MODEL_PROVIDER=openai
FLARE_MODEL_BASE_URL=https://api.deepseek.com/v1
FLARE_MODEL_NAME=deepseek-chat
FLARE_MODEL_API_KEY=sk-xxx
```

### 让它真正干活（工作区）

控制台选工作区 → 「添加工作区…」→ 选一个服务器目录（例如放了个项目的文件夹）。然后对 Agent 说 *"读一下这个项目的 README，总结它做什么"* 甚至 *"帮我写个 hello.py 并运行"* —— 它会真的读文件、写文件、跑命令，每步都显示在对话里。

---

## 🧩 架构

```mermaid
flowchart LR
    subgraph Web[React 控制台]
        UI[对话/工作区/知识库/审批/模型/运维]
    end
    subgraph Runtime[FastAPI 进程]
        API[/v1/tasks /v1/workspaces ...]
        TM[TaskManager<br/>LangGraph 编排 + SSE 实时流]
        ST[(SQLite<br/>任务/知识库/记忆)]
        GW[模型网关<br/>mock/openai/anthropic + 重试]
        TR[ToolRegistry<br/>工具注册表]
        AP[审批门 + TOFU]
    end
    UI <-->|SSE/HTTP| API
    TM <--> ST
    TM --> GW --> M[(DeepSeek/通义/Claude<br/>vLLM/Ollama...)]
    TM --> AP
    TM --> TR
    TR --> WS[工作区六工具<br/>read/write/edit/glob/grep/bash]
    TR --> KB[RAG 知识库]
    TR --> MEM[分层记忆]
    TR --> MCP[MCP 网关]
    TR --> SUB[多 Agent 子任务]
```

**一次任务怎么走**：`POST /v1/tasks` 立即返回 `task_id` → 后台协程用 LangGraph 跑 Agent（模型思考 → 调工具 → 观察 → 再思考）→ 每一步 `step/token` 事件经 SSE 实时推给前端 → 终态补 `result`。期间若工具触发审批，任务挂起为 `awaiting_approval`，等你在控制台批/拒后自动续跑。

---

## 📁 目录结构

```
services/
  agent_runtime/     FastAPI 主应用：任务编排(tasks.py)、审批(approval.py)、
                     工作区(workspace_fs.py)、模型配置(model_config.py)、路由(routes/)
  model_gateway/     模型网关：provider 抽象 + openai/anthropic 兼容 + 重试
  tools_gateway/     工具注册表(registry.py) + 工作区六工具(workspace_tools.py)
  rag/               知识库：入库管线 / 混合检索 / 评测
  memory/            分层记忆：事实 + 向量 + 会话上下文
  sandbox/           本地子进程沙箱（未来可换容器）
  mcp/               MCP 网关（服务器配置 + 工具桥接）
  skills/            技能包注册与加载
  subagent/          多 Agent 子任务运行时
  flare_common/      配置(12-factor) / 错误契约 / 日志 / 指标 / 租户
  flare_cli/         命令行入口（flare）
  web/               React 控制台（Vite + Tailwind v4 + shadcn/Radix）
tests/               265 个测试（unit + API + 全链路）
data/                运行数据（tasks.sqlite3 / kb.sqlite3 / memory*.sqlite3 / skills/）
```

---

## 📚 教学文档（有基础的人就能看懂）

从零到能跑通、能改、能加功能：

| 章节 | 内容 |
| --- | --- |
| [00 · 认识 Flare Agent](docs/guides/00-overview.md) | 是什么、能做什么、设计理念、和 DSH/Claude Code 的区别 |
| [01 · 快速开始](docs/guides/01-quickstart.md) | 安装、启动、发第一个任务、接真实模型、建工作区 |
| [02 · 核心概念](docs/guides/02-core-concepts.md) | 任务/线程/SSE 流式/工作区/工具/审批/权限模式/模型 |
| [03 · 架构详解](docs/guides/03-architecture.md) | 真实架构图 + 模块职责 + 代码地图 + 一次任务的数据流 |
| [04 · 二次开发](docs/guides/04-developer-guide.md) | 加一个工具 / 加一个 API / 前端构建 / 跑测试 / CLI |
| [05 · 进阶主题](docs/guides/05-advanced.md) | 模型配置 / 权限策略 / 工作区代码能力 / RAG / 记忆 / 多 Agent / MCP / 技能 / 运维 |

> 另有规划与评审文档（ADR、产品架构、压测、面试题库）见 [docs/README.md](docs/README.md)。

---

## 🗺️ 路线图

| 里程碑 | 内容 | 状态 |
| --- | --- | --- |
| M0–M1 | 项目准备 + 需求/架构评审（ADR ×15） | ✅ |
| M2 | 核心 Agent 引擎：任务编排 + 工具系统 + 工作区 + 审批 + Web 控制台 | ✅ 真实交付 |
| M3 | RAG + 分层记忆 + 评测 | 🔨 已可用（SQLite 版），云原生向量库规划中 |
| M4 | 容器沙箱（Docker/Kata）+ 生产部署（ACK/OSS） | ⏳ 规划 |
| M5 | 多实例（Redis 共享）+ 可观测增强 + 多租户 | ⏳ 部分（Redis 存储已支持） |
| M6 | 生产运营：容量 / 成本 / SLO 运营 | ⏳ 指标与 SLO 已埋点，运营流程规划中 |

## 🤝 参与贡献

欢迎贡献！请先阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 与 [Code of Conduct](CODE_OF_CONDUCT.md)：

- 分支命名 `feat/<module>-<desc>`，提交遵循 Conventional Commits
- PR 需过 CI（lint / 测试 / 扫描）与 Eval（AI 相关改动）
- 安全漏洞请走 [SECURITY.md](SECURITY.md) 私有通道

## 📄 License

[MIT](LICENSE) © 2026 Syotick
