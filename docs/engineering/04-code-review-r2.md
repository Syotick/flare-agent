# 代码审查 Round 2 — ReAct 核心循环交付（M2-4b）

> 审查对象：agent_runtime/graph.py + checkpoint.py + model_gateway/mock.py + tests/unit/test_graph.py
> 验证：pytest 全绿 + 6 探针实测；提交见 git log（F1-F4 逐条修复）。

## 结论

图结构与解耦方向正确（agent_runtime 只向下依赖 ModelProvider/Registry）。发现 1 高危健壮性缺陷、1 预算 off-by-one、1 隐式协议、1 双重静默降级，全部修复。

## 处置明细

| 编号 | 严重度 | 意见 | 处置 | 落实 |
| --- | --- | --- | --- | --- |
| F1 | 高危 | 模型决策里未知工具/非法参数直接击穿 agent（registry 前置检查是抛异常，executor 未捕获） | tool_executor 捕获 NotFoundError/ValidationError → 转 ToolResult(ok=False, UNKNOWN_TOOL/INVALID_ARGS) 结构化观察回灌，模型可重试/换路 | 已修复 + 2 测试 |
| F2 | 中 | 预算 off-by-one：最后观察回灌后模型永远没机会收尾（max_steps=1 永不 completed） | actor 改 step > max_steps；executor 用条件边熔断（step >= max_steps 直接到 END），末次观察后模型必有决策机会 | 已修复 + 边界测试 |
| F3 | 中 | 决策 JSON 两处手写、无类型契约；坏决策静默当答案（违 fail-fast） | 新增 pydantic ToolCallDecision（action Literal + call_tool 必须带 tool）为共享契约；mock 产出/图解析都走它；坏决策 → 日志 + INVALID_MODEL_OUTPUT 观察回灌 | 已修复 + 2 测试 |
| F4 | 中 | checkpoint 双重静默降级（except 吞错 + 非 dev 直接 MemorySaver）+ SQLite 无测试 + 连接不缓存 | 降级路径 logger.warning；非 dev 未接 Postgres → NotImplementedError fail-fast；进程级单例缓存；_create_sqlite_saver 供测试 + 跨实例持久化冒烟测试 | 已修复 + 2 测试 |

## Round 3 复查清单

- [ ] 端到端回路接线：graph + checkpointer 接入 app.py / Web（R6/审查第 8 条，M2-4c）
- [ ] 记忆/文档已同步：CLAUDE/AGENTS 记 M2-4b 完成 + pytest 25 + 本记录
- [ ] （保留）真实模型接入前，确认 _parse_decision 的 JSON 契约可平滑映射到 OpenAI function-calling（M4）
