# 02 · 核心概念

> 目标读者：已经把 Flare Agent 跑起来、想理解它内部机制的人。
> 读完本篇你会：**明白任务/线程/流式/工作区/工具/审批/权限/模型这八个概念**，知道它们对应哪些 API。

---

## 1. 任务（Task）——一切从一句话开始

你发的每一条消息 / 指令 = 一个任务。后端收到后**立即返回**，后台用 LangGraph 编排执行（不阻塞请求）：

```bash
curl -X POST http://127.0.0.1:8000/v1/tasks \
  -H 'Content-Type: application/json' \
  -d '{"task_input":"帮我写个 hello.py","workspace_id":"D:/projects/demo"}'
```

返回 `task_id` + `status=running`。任务状态流转：`running → completed / failed / budget_exceeded / awaiting_approval`。

- **会话 = 任务**：侧栏每条会话就是一个任务记录
- **重命名**：`PATCH /v1/tasks/{id}`（只改显示名，不改原始输入）
- **删除**：`DELETE /v1/tasks/{id}`（直接删，不是归档）
- **持久化**：任务落在 SQLite（`data/tasks.sqlite3`），重启可查

## 2. 线程（thread_id）——续聊的上下文

同一会话里继续发消息 = 同一个线程。后端用 LangGraph checkpointer 保存线程状态，下次请求自动带上历史对话，实现**上下文连续**：

```json
// 第一条：不传 thread_id，后端自动生成并返回
{"task_id":"a","thread_id":"t1","status":"running","workspace_id":"default"}

// 续聊：把 t1 传回来
{"task_input":"继续","thread_id":"t1","workspace_id":"default"}
```

## 3. SSE 实时流——过程看得见

`GET /v1/tasks/{id}/stream` 用 SSE 推事件，前端订阅后实时渲染。事件类型：

| 事件 | 含义 | 前端表现 |
| --- | --- | --- |
| `token` | 模型吐的一段文本 | 打字机追加 |
| `step` (`actor`) | 模型决定调工具 / 出最终结果 | 工具卡片 / 结果 |
| `step` (`tool_executor`) | 工具执行结果 | 工具卡片变"成功/失败" |
| `approval` | 工具触发审批 | 审批卡片 |
| `approval_decision` | 你批/拒了 | 审批卡片更新状态 |
| `result` | 任务结束 | 收尾 |

## 4. 工作区（workspace_id）——Agent 的活动范围

工作区 = **服务器上的真实目录**。选目录的方式就是浏览器里点「添加工作区」→ 目录选择器。

- 工作区 ID 就是目录的绝对路径（如 `D:/projects/demo`）
- 工作区下的会话列表：`GET /v1/tasks?workspace=<路径>`
- 目录浏览：`GET /v1/workspaces/dirs?path=`（根级返回盘符，对标 DSH host.listDirectory）
- 删除工作区 = 清空该目录下的会话（**不删磁盘目录**）

没选工作区时 Agent 只有通用工具，**没有**读写文件 / 跑命令的能力（防越权）。

## 5. 工具（Tool）——Agent 的手

工具 = 名称 + 描述 + 参数 Schema(JSON Schema) + 异步执行函数。集中注册在 `ToolRegistry`（`services/tools_gateway/registry.py`）。

选定了真实目录工作区后，Agent 自动获得 **工作区六工具**（`services/tools_gateway/workspace_tools.py`）：

| 工具 | 作用 | 权限 |
| --- | --- | --- |
| `read` | 读文件（限 2000 行） | read |
| `write` | 写文件（覆盖已存在文件前必须先 read） | write |
| `edit` | 精确替换（需先 read，带 size+mtime 版本校验） | write |
| `glob` | 按模式找文件（最多 100 个） | read |
| `grep` | 搜内容（最多 250 条） | read |
| `bash` | 跑命令（Git Bash，30s 超时默认，输出 64KB 截断） | destructive |

关键安全行为：**write/edit 的目标在工作区外 → 拒绝**（OUT_OF_BOUNDS）；bash 走审批兜底。

## 6. 审批（Approval）——危险操作你点头

- 工具权限分级：`read < write < destructive`
- 审批策略：`FLARE_APPROVAL_REQUIRE_LEVEL`（默认 `destructive`，即写/破坏性需要审批；可改 `write` 让所有写也审批）
- **TOFU（首用信任）**：同一会话内某个工具获批过一次，后续自动放行——不会每个文件都问你一次
- 挂起时任务状态 `awaiting_approval`，你在控制台批/拒（`POST /v1/approvals/{id}/decide`），批了自动续跑

## 7. 权限模式（Permission Mode）——整会话的松紧度

Composer 顶部第一个 chip，三个档位：

| 模式 | 行为 |
| --- | --- |
| 🔒 只读 | 只注入只读工具（read/glob/grep），write/edit/bash **物理不存在**，且免审批 |
| 🛡 批准 | 默认：写/破坏性操作逐次审批 |
| ⚡ 无限制 | 跳过审批门，全部自动执行 |

> 只读不是"不让写"，而是"没有写的能力"——最彻底的隔离。

## 8. 模型（Model）——Agent 的脑子

- **默认激活模型**：控制台「模型」页配置（`data/model_config.json` + 环境变量优先）
- **会话级选择**：Composer 第二个 chip 可给**每个任务**指定自定义模型 profile（`POST /v1/tasks` 传 `model` 字段），配置无效自动回退默认模型
- 供应商：`mock` / `openai`（兼容 DeepSeek/通义/vLLM/Ollama）/ `anthropic`
- 网关带**瞬态重试**（网络/超时/5xx 指数退避）

## 9. 存储（Store）——数据都在哪

| 数据 | 位置 | 配置项 |
| --- | --- | --- |
| 任务/会话 | `data/tasks.sqlite3` | `FLARE_TASK_STORE=memory|sqlite|redis` |
| 知识库 | `data/kb.sqlite3` | — |
| 记忆 | `data/memory*.sqlite3` | — |
| 模型配置 | `data/model_config.json` | `FLARE_MODEL_CONFIG_PATH` |
| 技能 | `data/skills/` | `FLARE_SKILLS_DIR` |

## 下一步

→ [03 · 架构详解](03-architecture.md)：模块怎么组织、一次任务在代码里怎么走完。