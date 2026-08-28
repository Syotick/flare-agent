# MCP 客户端与 Skills 机制（FR-2 / FR-3）

> 版本：v1.0 ｜ 日期：2026-08-28 ｜ 状态：draft ｜ 配套实现：services/mcp + services/skills

## 一句话

**MCP = 生态接入的标准插座，Skills = 声明式上下文资产**。本课讲我们如何落地
（实践）与为什么这样设计（真理），对应 FR-2 工具系统与 FR-3 Skills。

---

## 1. 实践：MCP 客户端（FR-2.2 / FR-2.3）

### 1.1 是什么

Model Context Protocol 本质是 **JSON-RPC 2.0 over HTTP**：客户端 initialize 握手 →
tools/list 拿工具清单 → tools/call 调用。传输有两种常见形态：

- **Streamable HTTP**（2025 现代标准）：POST JSON-RPC，单响应或 SSE 流；
- **HTTP+SSE**（经典形态）：GET 事件流发现 endpoint，POST 消息，响应经事件流回传。

### 1.2 落地结构（services/mcp）

| 模块 | 职责 |
| --- | --- |
| protocol.py | JSON-RPC 消息形状 + 方法常量 + 错误类型（零依赖） |
| client.py | McpClient + 传输层（Streamable HTTP / SSE，httpx） |
| adapter.py | MCP 工具 → ToolRegistry.Tool（命名空间 mcp__<server>__<tool>） |
| gateway.py | McpGateway：多服务器、白名单、认证头、审计、幂等注册 |
| mcp_tools.py | mcp_connect / mcp_list 内置工具 |
| testing.py | FakeTransport（进程内）+ MemoryMcpServer（真实 HTTP，stdlib 零依赖） |

### 1.3 关键设计点

1. **协议层与传输层分离**：传输可插拔（Fake / 真实 HTTP / 未来官方 SDK），协议层不动。
2. **命名空间隔离**：外部工具名带前缀，防撞名/防伪装；inputSchema 直接复用统一校验层。
3. **网关是唯一入口**（FR-2.3）：禁止 Agent 直连外部 server；白名单（服务器级 + 工具级）
   + 认证头注入 + 审计钩子，限流/配额随 M5/M6 在此层扩展。
4. **fail-fast 握手**：不初始化直接 tools/list 属未定义行为，连接失败显式抛错不静默。
5. **按需连接**：默认不连任何服务器（FLARE_MCP_SERVERS=[] 无行为变化）；
   Agent 调 mcp_connect 拉取工具，幂等注册。

### 1.4 演示

```bash
PYTHONPATH=services python scripts/demo_mcp.py   # 进程内真实 HTTP MCP Server + 接入
```

配置真实服务器（环境变量）：

```json
FLARE_MCP_SERVERS=[{"name":"srv","url":"http://host:8080/mcp","transport":"streamable_http","headers":{"Authorization":"Bearer x"},"enabled":true}]
```

## 2. 实践：Skills（FR-3.1 / FR-3.2）

### 2.1 是什么

技能 = **声明式上下文资产**（对齐 Codex SKILL.md 心智）：一个目录含 SKILL.md
（frontmatter 元信息 + 指令正文）+ 可选 resources/。它不是可执行黑盒，
而是"模型照着做的指令"，激活 = 注入 Agent 上下文。

### 2.2 落地结构（services/skills）

| 模块 | 职责 |
| --- | --- |
| frontmatter.py | SKILL.md 元信息解析（零依赖 YAML 子集，fail-fast） |
| loader.py | 技能包目录 → Skill 值对象（指令 + 资源 + 依赖工具） |
| registry.py | SkillRegistry：安装/卸载/列表/build_context |
| skill_tools.py | skill_list / skill_load 工具 |

### 2.3 关键设计点

1. **技能是上下文资产不是代码**：skill_load 返回可回灌文本，不产生执行副作用。
2. **可执行部分仍走 ToolRegistry**：技能声明 required_tools，工具注册表统一执行。
3. **声明式契约 fail-fast**：坏 SKILL.md（缺 name/description、frontmatter 未闭合）
   解析即报错，不静默当空技能。
4. **存储演进**：本地文件系统 → OSS + 签名/版本化（FR-3.2，随对象存储落地）。

### 2.4 演示

```bash
PYTHONPATH=services python scripts/demo_skills.py  # 安装示例 code-review 技能 -> 列表 -> 加载
```

## 3. 真理：为什么"生态接入"是成熟产品的标配

1. **生态而非自建**：成熟产品（Codex/DSH/Grok）都接入 MCP——Agent 的能力上限 =
   可接入的外部工具数，而不是内置工具数。
2. **信任边界在网关**：外部工具视为不可信输入源，白名单/认证/审计在网关层做，
   工具适配只做形状转换、不做特权放大。
3. **上下文预算（F4.3 联动）**：技能指令不能无限堆进 system——按需 skill_load，
   用完即弃，配合上下文工程封顶。
4. **面试考点**：MCP 协议握手/传输、工具 schema 注入、技能包声明式设计、
   外部工具安全（注入/越权）都是高级 Agent 工程师高频考点——本模块就是可讲的落地案例。

## 4. 下一步

- MCP 网关补限流/配额/审计落库（M5/M6 层）
- 技能市场（租户共享/跨租户模板 + OSS 存储 + 哈希签名校验，FR-3.2）
- 多 Agent 并行（F1.4）：Subagent 编排，MCP/Skills 作为子任务的共享上下文

