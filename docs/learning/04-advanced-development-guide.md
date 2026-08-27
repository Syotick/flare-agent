# Flare Agent · 进阶开发指南（实践 + 真理）

> 版本：v1.0 ｜ 日期：2026-08-27 ｜ 状态：draft
> 定位：教你在 Flare Agent 上安全地加功能——加工具、加 API、接真实模型、换存储底座，以及测试纪律与踩坑合集。
> 前置：先读 [01-agent-interview-questions](./01-agent-interview-questions.md) 理解 Agent 核心概念，再读本指南动手。

---

## 1. 架构分层与依赖方向（先看清地图）

- 真理：可拓展的代码 = 清晰的依赖方向 + 稳定的协议（接口）+ 可插拔的实现。改一层不碰别层，
  是"能加功能"和"能上线"的分水岭；反过来，依赖乱 = 加个功能牵一发动全身。
- 实践（services/ 分层，箭头 = 允许的依赖方向）：

    flare_common（错误/配置/日志）——最底层，谁都能依赖
        ^  ^  ^
        |  |  +---> rag（chunking/embedder/store/pipeline，RAG 底座）
        |  +------> memory（事实库 + 复用 rag 协议的向量记忆 + 上下文工程）
        +---------> model_gateway（ModelProvider 协议 + mock） / tools_gateway（Tool/Registry）

    agent_runtime（图 + 任务 + 路由）依赖上面全部；sandbox（M4 沙箱）独立；web（前端）独立。
- 规则：上层可依赖下层，下层绝不依赖上层；新增一个包必须同步加进 pyproject.toml 的
  packages.find include——否则 `pip install -e .` 出的 wheel 不含它，开发（PYTHONPATH）能跑、
  生产镜像装上就跑不了。踩坑实录：memory* 曾漏掉，已补（M5 上镜像前必查）。

## 2. 手把手：加一个 Agent 工具（约 10 分钟）

- 真理：工具是 Agent 的"手"。一个工具只暴露一个动作；参数用 JSON Schema 描述（模型靠它猜参数）；
  失败返回结构化 ToolResult（带 error_code），绝不抛异常——坏决策要回灌给模型重试，不是崩掉任务。
- 步骤：
  1. 写 async 函数 `async def func(args) -> ToolResult`；
  2. 用 Tool(name, description, parameters, func) 包装（description 要写"什么时候用"，模型据此决策）；
  3. 在 create_app 的默认注册表或你自己的 App 里 registry.register(tool)；
  4. 图首轮会自动把工具 schema 拼进 system 消息（graph._build_tool_schema，R1 修复）——模型看得见才谈得上自主调用；
  5. 写测试：registry.execute 直测 + Agent 端到端（会读 system 提示的假模型，见 test_rag.py 的 _ToolAwareProvider）。
- 真实示例（services/memory/mem_tools.py 的 mem_set）：

    async def _mem_set(key: str, value: str) -> ToolResult:
        fact = await memory.remember_fact(key, value)
        return ToolResult(ok=True, content=f"已记住 {key}={fact.value[:80]}")
    tool = Tool(name="mem_set", description="把一条长期事实写入项目记忆…",
               parameters={"type":"object","properties":{...},"required":["key","value"]},
               func=_mem_set)

- 参数校验：registry.execute 用 jsonschema 校验，模型给错参数 → INVALID_ARGS 观察回灌（test_graph 有覆盖）。

## 3. 手把手：加一个 API 路由

- 真理：FastAPI 路由 = 薄适配层，业务逻辑在 service 层；错误契约统一 FlareError -> {code, message, request_id}。
  路由不碰存储实现，只接收注入的依赖（可测试、可隔离）。
- 步骤：
  1. routes/xxx.py 定义 `build_xxx_router(deps) -> APIRouter`（如 build_memory_router(memory)）；
  2. app.py 的 create_app 接收注入依赖并 include_router（默认值留给测试/开发）；
  3. main.py 组装真实持久化（data/*.sqlite3）；
  4. 用 TestClient 的 with 块写 API 测试。
- 本仓库最痛的测试坑（写进脑子的纪律）：**TestClient 必须用 `with TestClient(app) as client:`**。
  不用 with 块 = 每次请求临时 portal loop，后台 asyncio.create_task 被孤儿 loop 丢弃 → 任务卡"running"、
  event_count 永远 0。所有 Agent/任务类测试都必须遵守（M5 迁 Redis/DB 前都是硬约束）。

## 4. 手把手：接入真实模型（M4 前置）

- 真理：模型是"会推理的大脑"但每次调用无状态——Agent 的记忆/工具/预算都在图里，模型只负责"下一步想什么"。
- 现状：model_gateway.MockModelProvider（回显 + 固定决策 stub）用于开发/测试；
  providers.ModelProvider 协议定义 chat/stream 两个方法。
- 接入真实模型 = 实现该协议 + 把模型输出的 JSON 决策（call_tool/final）与 function-calling 对齐（M4 换 _parse_decision）。
- 纪律：开发期 mock 够用；上线前必须真实模型，API Key 走 Secret 不进镜像。

## 5. 存储协议可插拔（换底座不动上层）

- 真理：同协议换实现 = 换底座。上层只依赖协议，不依赖具体存储——这是"开发 SQLite、生产云底座"的底气。
- 实践：
  - rag.Embedder（embed(texts)）+ rag.VectorStore（add/search/delete）两个 Protocol；
    开发 HashEmbedder + SqliteVectorStore；生产 DashScopeEmbedder + PgVectorStore（未配置 fail-fast 503，不静默降级）；
  - checkpointer：LangGraph BaseCheckpointSaver——dev SQLite（data/flare_agent.sqlite3）、prod AsyncPostgresSaver（M5）；
  - 换实现的正确姿势：新增实现类实现协议 → 在 main.py 替换 → 跑全量测试，上层零改动。
- 踩坑实录：MemorySaver.aget 返回的是 dict，状态在 channel_values 而不是 values（M1 修复）——
  写通用存储代码要兼容不同 saver 的结构差异（dict / 对象都兜底）。

## 6. 测试纪律与踩坑合集

- pytest：asyncio_mode=auto（async 测试自动跑）、pythonpath=["services"]、TestClient with 块（上面已讲）。
- aiosqlite：连接绑定创建它的 loop，不能跨 loop 共享；取行用 `cur = await db.execute(...); rows = await cur.fetchall()`。
- Python 内置 hash() 每次进程加盐 → 确定性嵌入用 zlib.crc32（RAG 可复现的关键）。
- 写文档/脚本的转义坑：模板字面量里的反斜杠 n 会被求值为真换行——用 chr(10) 拼接或纯 print() 分段。
- 静态检查：ruff（E/F/W/I/UP/B/SIM，line-length 100）+ black（line-length 100）都要干净；提交前 pytest 全绿。
- "假抽象"警示（M1 教训）：接口要么接线要么删掉。assemble 的 recent 参数曾没有任何调用方 = 死代码，
  文档还宣称三层记忆——被审查抓出来。新加的参数必须立刻有真实调用路径 + 测试。

## 7. 开发 → 生产切换矩阵

| 项 | 开发默认 | 生产 | 切换点 |
| --- | --- | --- | --- |
| 模型 | mock 供应商 | 真实模型（OpenAI/DeepSeek/DashScope 协议） | M4 |
| 嵌入 | HashEmbedder（字面 n-gram） | DashScope text-embedding-v3 | M3c/M4 |
| 向量库 | SqliteVectorStore | PgVectorStore（同库分表 kb_chunks/memory_chunks） | M5 |
| 事实/记忆 | SQLite facts 表 | PG 同结构 | M5 |
| checkpointer | SQLite | AsyncPostgresSaver | M5 |
| 任务存储 | 进程内 dict | Redis/DB | M5 |
| 对象存储 | 本地/内存 | OSS（FLARE_OBJECT_STORE_* 已预留） | M5 |
| 前端 | Vite dev (5173) | 构建产物静态托管（Nginx/CDN） | M2 已支持 dist 挂载 |
| 可观测 | 控制台日志 | OTel → SLS/ARMS/Prometheus | M5/M6 |

## 8. 练习

1. 给 Agent 加一个"记 TODO"工具（TODO 列表按 project 存 SQLite），并让模型能看到它：注册、system 注入、端到端测试。
2. 把 kb_search 的返回从 300 字符观察改成"带预算的引用摘要"（提示：复用 memory.context 的 summarize）。
3. 写一个 PgVectorStore 骨架（实现协议即可，内部用 asyncpg），让上层零改动跑通——体会"换底座"的承诺。
