# OpenAI 兼容 API 与 CLI（F9.2/F9.3）

> 版本：v1.0 ｜ 日期：2026-08-28 ｜ 状态：draft ｜ 配套实现：routes/openai_compat.py + services/flare_cli

## 一句话

把 Agent 能力包装成 **OpenAI 兼容的 Chat Completions 端点**（任何 OpenAI SDK / LiteLLM /
curl 零改造成本接入）+ 一个对标 Claude Code 的 **CLI 瘦客户端**——这是把 Agent"产品化"的接入形态。

---

## 1. 实践

### 1.1 OpenAI 兼容 REST API（F9.3，services/agent_runtime/routes/openai_compat.py）

| 端点 | 说明 |
| --- | --- |
| POST /v1/chat/completions | 标准 Chat Completions 契约（含 stream=true 的 SSE 分块 + [DONE]） |
| GET /v1/models | 模型列表（OpenAI 客户端启动时先调它） |

请求形状与 OpenAI 完全一致：
\`\`\`json
{"model": "flare-agent", "messages": [{"role": "user", "content": "帮我把周报拆成三点"}], "stream": true}
\`\`\`
响应：{id: "chatcmpl-<task_id>", object: "chat.completion", choices: [{message: {role, content}, finish_reason}]}，
流式：逐 chunk + data: [DONE]。

设计要点：
1. **复用 TaskManager**：任务照常登记/可观测/可查（与 /v1/tasks 同一套存储与指标），
   非流式请求内部轮询等到任务完成——"同步语义的异步执行"。
2. **消息→任务**：取最后一个 user 消息内容作为 task_input（Agent 工具调用发生在内部）。
3. **认证**：FLARE_API_KEY 配置后要求 Authorization: Bearer（未配置=开放，生产必配）。
4. **错误**：OpenAI 风格扁平 \`{"error": {message, type, param, code}}\`（不经过 FastAPI 的 detail 包装——
   这是最容易踩的坑：HTTPException 会被包成 {"detail": ...}，不符合 OpenAI 契约）。

### 1.2 CLI（F9.2，services/flare_cli）

\`\`\`bash
python -m flare_cli chat "帮我把周报拆成三点"      # 流式输出（OpenAI 兼容端点）
python -m flare_cli --json chat "hello" --no-stream
python -m flare_cli tasks                         # 最近任务列表（原生 /v1/tasks）
python -m flare_cli task <task_id>                # 任务详情
python -m flare_cli models                        # 模型列表
\`\`\`
- 连接：默认 http://127.0.0.1:8000，可 --url / FLARE_URL 覆盖；--api-key / FLARE_API_KEY 认证
- 实现：httpx 瘦客户端（FlareClient），可注入 httpx.ASGITransport 直连应用测试（不启真实服务器）
- 安装为 console script：\`pip install -e .\` 后可直接 \`flare chat ...\`

### 1.3 冒烟（真实服务器）

\`\`\`bash
uvicorn agent_runtime.app:create_app --factory --port 8137 &
python -m flare_cli --url http://127.0.0.1:8137 chat "你好，请回复我"
\`\`\`

## 2. 真理

1. **OpenAI 兼容 API 是生态的事实标准**：工具生态（LiteLLM、OpenAI SDK、各类编排器、第三方
   Agent 平台）都按这个契约集成——做兼容端点等于"免费获得整个生态的客户端"。
2. **接入形态是产品化的临门一脚**：Web 控制台服务人类、OpenAI 兼容 API 服务机器/开发者、
   CLI 服务终端重度用户——三端同一套后端（这是 FR 里程碑"Web/CLI/API 三端"的验收点）。
3. **同步语义的异步执行**：Agent 任务是异步批处理（工具调用多轮），但对外给 OpenAI 的
   "同步请求-响应"体验——内部 create + 轮询，这是封装异步系统为同步契约的通用模式。
4. **面试考点**：OpenAI 兼容协议（消息/工具/流式 chunk/错误契约）、CLI 设计（子命令/配置/
   错误码/可测试性）、三端复用同一后端。

## 3. 下一步

- 工具调用透出：把 Agent 的工具决策暴露为 OpenAI tools/function-calling 契约（客户端可编排）
- 模型路由：model 参数映射到 F6.1 多模型路由（按模型名选 provider）
- CLI 增强：项目记忆（AGENTS.md）、diff 预览、权限提示（对标 Claude Code）
- token 预算：max_tokens 真正约束上下文（当前 MVP 只做步骤预算）

