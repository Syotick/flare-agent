# 多 Agent / Subagent 并行（F1.4）

> 版本：v1.0 ｜ 日期：2026-08-28 ｜ 状态：draft ｜ 配套实现：services/subagent

## 一句话

**把一个大任务拆成多个独立子 Agent 并行执行、再收集汇总**——这是 DSH 的招牌、
Codex 云并行任务的核心，也是高级 Agent 工程的核心考点。本课讲我们怎么落地（实践）
与为什么这样设计（真理）。

---

## 1. 实践：SubagentRuntime + 四个编排工具

### 1.1 是什么

子任务 = **独立的 ReAct Agent 实例**（复用 build_react_agent）：有自己的一套
LangGraph 图、独立状态、独立预算（max_steps）、独立超时，进程内以 asyncio
后台任务并发跑。父 Agent 不阻塞，spawn 一批 → 并行收集 → 自行汇总。

### 1.2 落地结构（services/subagent）

| 模块 | 职责 |
| --- | --- |
| runtime.py | SubagentRuntime：spawn / _run（独立图 + MemorySaver）/ await / run_subagents（gather）/ list / close |
| sub_tools.py | spawn_subagent / await_subagent / list_subagents / run_subagents 四个工具 |

### 1.3 编排工具

| 工具 | 作用 |
| --- | --- |
| spawn_subagent(prompt) | 派生子任务，立即返回 id（后台跑，不等待） |
| await_subagent(id) | 等待某子任务完成并取回输出 |
| list_subagents() | 列出所有子任务状态（可观测） |
| run_subagents(prompts) | **并行核心**：spawn 全部 + asyncio.gather 收集 |

模型端用法（真实 LLM 自主决策）：
1. 拆解：把大任务拆成 N 个独立子任务描述；
2. 并行：调 run_subagents({prompts:[...]}) 一次性并行执行；
3. 汇总：把返回的 N 个结果在后续决策里整合成最终答案。

### 1.4 关键设计点

1. **复用而非重写**：子 Agent 直接复用 build_react_agent——同一套 ReAct 循环、
   工具注册表、决策契约。多 Agent 不是新引擎，是"同一个 Agent 的多个实例"。
2. **并行靠 asyncio.gather**：spawn 不等待（asyncio.create_task），collect 用
   gather 并发等待——单线程事件循环里天然并发（I/O 型工具并行）。
3. **预算/超时独立**：每个子任务独立 max_steps 与 timeout，防单点失控拖垮全局。
4. **护栏**：存活子 Agent 数量上限 MAX_ACTIVE=64（防失控扇出）；单次
   run_subagents 上限 16 个 prompt。
5. **临时性**：子任务用 MemorySaver 进程内 checkpointer，结果以文本收集、
   不落任务存储（避开 dev SQLite checkpointer 长连接锁文件坑）。
6. **嵌套允许但有界**：子 Agent 共享工具注册表（可见 spawn/run），支持嵌套编排，
   由数量上限 + 每层步数预算兜底。

### 1.5 演示

```bash
PYTHONPATH=services python scripts/demo_subagent.py
```

## 2. 真理：为什么"多 Agent 并行"是成熟产品的核心

1. **能力边界**：单个 Agent 的上下文与步数有限；并行把"线性执行"变成"分而治之"，
   是扩展单次任务处理规模的根本手段（Codex 云并行、DSH subagent/workflow）。
2. **隔离与容错**：子任务独立状态/预算/超时——一个子任务失败/超时不影响其他，
   父 Agent 拿到部分结果仍可汇总（结构化失败不炸父任务）。
3. **可观测**：子任务有生命周期记录（list_subagents），可审计每个子 Agent 干了什么。
4. **面试考点**：任务分解（task decomposition）、并行编排（fan-out/fan-in）、
   结果聚合、预算控制、嵌套深度限制——全是高频题，本模块就是可讲的落地案例。

## 3. 下一步

- 子任务接入任务存储（跨实例、断点续跑随 M5）
- 子 Agent 专属工具集（可见性裁剪，防子 Agent 越权用父的工具）
- 结果结构化（子任务返回 schema 而非纯文本，便于父 Agent 结构化汇总）
- 编排器：plan（自动拆解）→ execute（并行）→ synthesize（自动汇总）

