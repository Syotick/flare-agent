# 代码审查 Round 6 — 功能盘点文档 + MCP 客户端（FR-2.2/2.3）

> 审查对象：commit c3550ca（MCP 客户端 + Skills + 竞争对比文档，27 文件 +2192 行）
> 基线：test_mcp 13 例 + test_skills 9 例全绿；全量套件 1 个 flaky 失败（非本交付引入）。
> 处置：全部问题已修复，全量 160 测试全绿（新增 8 个 MCP 回归用例）。

## 结论

MCP 客户端是几轮里分层和解耦最干净的一个交付——协议/传输/适配/网关职责边界清晰、
fail-fast 与安全白名单到位、测试设施零依赖且覆盖真实 HTTP 双形态。主要问题集中在
两处"集成断点"（M1 图内 schema 冻结、M2 SSE 分块）和一处回归（flaky 测试），
恰好都是"宣称的功能在真实路径上不成立"——AI 局部最优模式的典型样本。

## 处置明细

| 编号 | 严重度 | 意见 | 处置 | 落实 |
| --- | --- | --- | --- | --- |
| M1 | 🔴 高 | 图内工具 schema 冻结：mcp_connect 中途注册的新工具对真实模型不可见（system 只首轮构建一次，function-calling 拿不到新 schema，直接路径通、集成路径断） | graph.py actor 每次进入都用当前 registry 重建 system 工具清单（原位替换，仅一条 system 消息）；补"经 ReAct 图端到端调用 mcp 工具"用例 | 已修复 + test_react_graph_mcp_connect_mid_task_end_to_end |
| M2 | 🟠 高 | SSE 跨 chunk 拆分必崩：_read_loop 每 chunk 后清空 buffer，半截事件被当完整事件解析失败丢弃 → 响应永不 resolve → 超时 | 新增 _split_sse_events 增量切分（只消费空行结尾的完整事件，残余保留在 buffer）；测试服务器支持 sse_chunk 分块写出 | 已修复 + test_sse_splitter_handles_cross_chunk + test_sse_real_server_cross_chunk |
| M3 | 🟠 中 | MCP 工具执行硬编码 10s 超时，且 McpClient._timeout 经 build_transport 时被丢弃（实际未生效）；网关无配置出口 | McpServerConfig.timeout 可配置 → _make_client 透传 → build_transport 透传 timeout 到传输层；app.py 从配置读 timeout | 已修复 + test_gateway_timeout_configurable_sse |
| M4 | 🟡 中 | mcp_connect(name) 与 register_all() 语义错位：connect 只连指定服务器，register_all 遍历全部 enabled，未连的刷无谓告警 | register_all(server_name=...) 过滤；mcp_connect 传 name | 已修复 + test_gateway_register_all_filter |
| M5 | 🟡 中 | mcp_list 直接摸网关私有成员 _configs/_clients/_registered_tools | 新增 McpGateway.status() 只读快照，mcp_list 改用 | 已修复 + test_gateway_status_readonly |
| M6 | 🟡 中 | 连接/注册动作本身不入审计（审计只挂工具调用） | connect 与 register 成功路径也调 audit 钩子 | 已修复 + test_gateway_audit_connect_and_register |
| M7 | 🟡 中 | MCP 工具输出不截断，观察消息可能撑爆上下文 | 观察内容限长 2000（对照 kb_tools 截断风格），全量进 artifacts.full_content | 已修复 + test_adapter_truncates_long_output |
| M8 | 🟡 低 | 白名单默认关闭需明示 | gateway 文档串 + learning/13 明示 allowed_servers=None=不限制，生产需显式开启 | 已修复（文档） |
| F1 | 🔴 高 | test_mem_recall_is_budgeted 时序 flaky：断言依赖 facts.updated_at 排序，time.time() 快速插入碰撞 → SQLite 等值排序不确定 | list_facts ORDER BY updated_at DESC, rowid DESC 确定性 tie-breaker（后插入的 rowid 更大视为更新）；14/14 × 3 遍稳定 | 已修复 |
| D1 | 🟡 低 | 决策快照已过时：功能盘点表仍写 MCP/Skills/多 Agent ⏳，而均已落地 | 文档 v1.1 刷新：标注决策时点 + 落地进度引用 | 已修复 |
| D2 | 🟡 低 | DSH star 数字 150k+ 与公开报道不符 | 改为不量化表述（"现象级增长"，注明公开报道与一手体验），附时点 | 已修复 |
| D3 | 🟡 低 | "八件套齐了"措辞过誉（用户体系/SSO/RBAC/配额仍 ⏳） | 措辞留余地，明确"骨架齐、能力逐项落地" | 已修复 |

## 做得好（保留，勿返工）

- 分层教科书级：protocol / client / adapter / gateway / mcp_tools / testing——协议层与网络 IO 分离、传输可插拔
- 错误模型清晰 + fail-fast：McpError 家族 → 结构化 ToolResult（MCP_FORBIDDEN / MCP_CALL_ERROR / MCP_TOOL_ERROR / MCP_NOT_CONNECTED）；initialize 失败、未知 transport、HTTP≥400、非 JSON 全部显式报错
- 安全边界到位：命名空间隔离 mcp__<server>__<tool> + 服务器级白名单 + 工具级白名单 + 认证头注入 + 审计钩子 + 禁止 Agent 直连
- 测试设施优秀：FakeTransport（进程内确定性）+ MemoryMcpServer（stdlib 真实 HTTP，Streamable + SSE 双形态，零外部依赖）
- 复用 tools_gateway 统一校验（inputSchema → Tool.parameters），非法参数 422 契约不变

## 下一轮复查清单

- [ ] M1 终验：接真实 LLM（function-calling）后，模型中途 mcp_connect 能正确格式化 mcp__* 调用（mock/序列 provider 已验，真实模型再验）
- [ ] M3 扩展：按工具分级超时（单工具 timeout 覆盖服务器级）
- [ ] 子 Agent（F1.4）专属工具集裁剪：子 Agent 不应默认可见父的全部工具（含 mcp_connect 等）
- [ ] MCP 结果结构化：服务器结构化内容（JSON）解析进 artifacts，不只是 text

