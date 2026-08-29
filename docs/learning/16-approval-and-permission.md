# 16 · 人机协作审批与工具权限分级（F1.3 / F2.4）

> 实践 + 真理 ｜ 配套需求：FR-1.3（人机协作审批）、FR-2.4（工具权限分级）
> 落地：services/agent_runtime/approval.py + graph.py 审批门 + routes/approval.py + Web 审批卡片

## 一、为什么需要

企业级 Agent 的核心约束是**可问责**：模型可以自主决策，但**破坏性动作必须经过人**。
产品形态对标 OpenAI Codex / Claude Code 的 permission prompt——Agent 想执行高敏感操作时
暂停下来，向人类展示"要做什么、为什么、参数是什么"，获批才动手，被拒则换路。

没有审批门的结果只有两种：要么所有工具直接执行（失控风险），要么干脆禁用敏感工具
（能力阉割）。审批门让"能做 + 受控"同时成立。

## 二、权限分级模型（F2.4）

权限是**工具的静态属性**，在注册时声明，与工具的实现/注册/执行完全解耦：

| 级别 | 含义 | 示例 | 默认是否要审批 |
| --- | --- | --- | --- |
| read | 只读，无副作用 | echo / kb_search / mem_recall / skill_list / mcp_list | 否 |
| write | 可写，低风险 | mem_set / skill_load / mcp_connect | 否 |
| destructive | 破坏性，高风险 | sandbox_run（执行任意代码） | ✅ 是 |

~~~python
# tools_gateway/registry.py
PERMISSION_READ, PERMISSION_WRITE, PERMISSION_DESTRUCTIVE = "read", "write", "destructive"

@dataclass(frozen=True)
class Tool:
    ...
    permission: str = PERMISSION_READ  # F2.4
~~~

策略（ApprovalPolicy）独立于工具声明：默认"等于或高于 destructive 需审批"，可收紧
（FLARE_APPROVAL_REQUIRE_LEVEL=write 则所有写/破坏性都要审批），或对个别工具加白名单
（extra_tools）。**审批门是编排层的横切能力**（tools_gateway 模块文档明确：
权限/限流/审计/审批做独立层，不塞进 ToolRegistry.execute）。

## 三、审批门实现（F1.3）：LangGraph interrupt

核心机制是 LangGraph 的 **interrupt / Command(resume)**：

1. 图内 tool_executor 执行工具前，先查 approval.requires_approval(tool)；
2. 需要审批 → 调 interrupt({...审批请求...})——**图在此挂起**（checkpointer 已落盘）；
3. 任务执行层看到 __interrupt__ 更新 → 登记审批请求、状态转 awaiting_approval；
4. REST POST /v1/approvals/{id}/decide 人工决策 → asyncio.Event 唤醒；
5. 执行层用 Command(resume={approved: True|False}) 续跑同一线程；
6. 图内 interrupt() 返回 resume 值：批准→真正执行工具；拒绝→把
   APPROVAL_REJECTED 观察回灌给模型，模型换路或收尾。

~~~python
# graph.py tool_executor（示意）
if approval is not None and approval.requires_approval(tool_obj):
    resume = interrupt({"type": "approval", "tool": tool_obj.name,
                        "description": tool_obj.description, "args": args,
                        "permission": tool_obj.permission})
    if not resume.get("approved"):
        return observation(APPROVAL_REJECTED)   # 拒绝观察回灌
result = await registry.execute(name, args)     # 批准后执行
~~~

~~~python
# tasks.py _execute（示意：中断恢复循环）
while True:
    async for update in agent.astream(pending_input, config, stream_mode="updates"):
        if "__interrupt__" in update:
            req = manager.register(task_id, ...)        # 登记审批
            task.status = "awaiting_approval"; save
            decision = await manager.wait(req.id)       # 等人工（asyncio.Event）
            pending_input = Command(resume=decision)    # 续跑
    else:
        break
~~~

## 四、关键坑（全踩过）

- **interrupt 是一次性流**：第一轮流在 __interrupt__ 后**结束**，不是停在那等你继续
  yield。执行层必须把"跑到 interrupt 为止"和"resume 续跑"拆成两段 astream。
- **resume 必须用同一 config**（thread_id 一致），否则会开新线程而不是续跑。
- **resume 值进 checkpoint**：必须是 JSON 可序列化的简单结构（approval_id 只用于登记，
  resume 传 {approved, reason} 即可）。
- **asyncio.Event 是单进程实现**：决策 REST 端点与执行协程同进程才有效。多实例/跨节点
  审批要上 Redis pub/sub（M5 演进，approval.py 已标注 TODO）。
- **审批超时是安全网不是主路径**：默认 300s 没人批 → 自动按拒绝处理，任务不无限挂起。
- **mock 环境的演示闭环**：默认 dev 模型只调 echo（read），永远触发不了审批。给 mock
  加了「沙箱执行」触发器（消息含该词 → 调 sandbox_run），让本地也能走通批准/拒绝两路。

## 五、真理（理论层）

- **Human-in-the-loop 三档**：①执行前审批（本实现，Pre-approval）②执行后审计
  （Post-hoc audit，拦不住破坏只留证据）③执行中确认（Streaming confirmation）。
  破坏性工具必须用 ①，这是"可问责"的底线。
- **TOFU（Trust On First Use）**：同一工具第一次要求确认，之后放行（防审批疲劳）——
  本期只做了"每次都审"，TOFU 是优化方向（approval_manager 留了 extra_tools 白名单）。
- **最小权限原则（Principle of Least Privilege）**：默认权限从 read 起步，按需升级。
  权限声明在 Tool 注册处最靠近真实风险（"哪个工具会做什么坏事"），审批策略只做门槛。
- **审批疲劳（Approval Fatigue）**：每一步都弹确认，人就会肌肉点批准，审批形同虚设。
  缓解：分级只对 destructive 审批 + 白名单 + 未来 TOFU。
- **与 checkpoint 的关系**：interrupt 挂起即 checkpoint，进程重启后能从中断点恢复——
  这比"执行协程 await 事件"更健壮（那是阻塞式挂起，不落盘）。本期两种都可用，
  选 interrupt 正是为了生产可恢复性。

## 六、端到端事件契约（前端依赖）

- 任务进入 awaiting_approval 后，SSE 推送 {type: "approval", data: {approval: {...}}}，
  Web 渲染审批卡片（工具名/权限/参数/描述 + 批准/拒绝按钮）。
- 决策后推送 {type: "approval_decision", data: {approval: {...status 已更新}}}，
  卡片状态回灌为 已批准/已拒绝/超时拒绝。
- 决策接口 POST /v1/approvals/{id}/decide：已处理请求重复决策返回 409（防重放）。
- 任务终态后 GET /v1/tasks/{id}/stream 完整重放，审批卡片随之恢复——SSE 回放是唯一数据源。

## 七、验收清单（FR-1.3 / FR-2.4）

- [x] Tool 权限分级（read/write/destructive），sandbox_run=destructive
- [x] 审批策略可配（级别 + 工具白名单 + 超时，环境变量 FLARE_APPROVAL_*）
- [x] 破坏性工具执行前 interrupt 挂起，任务状态 awaiting_approval
- [x] 批准放行 / 拒绝回灌观察（agent 换路）/ 超时自动拒绝
- [x] REST：列出待审批 / 详情 / 决策（重复决策 409 / 未知 404）
- [x] Web：对话流内审批卡片（批准/拒绝）+ 状态回灌 + SSE 重放恢复
- [x] 全量 190 测试全绿 + ruff/black 干净 + tsc/vite build + 真实服务器冒烟
