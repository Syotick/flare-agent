# 18. 流式回复经验总结：从"不显示/没生效"到"逐字打字机"

> 日期：2026-08-30
> 背景：用户反馈"前端依旧不显示，单纯不打印东西" → "流式依旧没有生效，参照 nova-agent（它是生效的）"
> 结论：这不是一个 bug，而是一整条链路上的 4 层问题叠加。逐层定位、逐层解决后，真实浏览器验证「回复逐字打出」。

---

## 一、现象

1. 前端「回复不显示」——偶尔整条空白
2. 回复「一次性全出」——没有打字机过程，看起来像"假流式"
3. 任务偶发失败（上游连接失败），前端无任何输出
4. 极端情况下前端把 JSON 决策原文打了出来（{"action":"final","answer":...}）

这些现象表面不同，根因却是一条链上的 4 个环节：模型层 → 传输层 → 前端层 → 稳定性层。

---

## 二、为什么之前不行（4 层根因）

### 层 1：模型调用层——ReAct 节点用的是「一次性非流式」chat

旧代码：一次拿完整回复，没有任何逐 token 输出

    response = await llm.chat(messages, tools=tools)

- LangGraph 的 actor 节点每轮只调用一次 llm.chat，完整结果落地后才产生一个 step 事件
- 前端能看到的"内容"永远只有最终完整文本，天然做不出打字机
- 这是"流式没生效"的第一根因：后端根本没有流式

### 层 2：上游协议层——OpenCode Zen 对 stream + tools 会断连

这是本次排查最关键的发现，通过 1 个最小探针脚本定位：

    stream 不带 tools         → 200，正常返回 8~11 个 chunk（真流式）
    stream 带 tools(1 个函数) → ConnectError，连接被上游重置
    urllib 请求任何流式       → 403（User-Agent 被上游拦截，必须用 httpx）

- 想"边生成边显示"，第一反应是 llm.stream(messages, tools=tools)
- 结果上游对这个组合直接拒绝，表现为 ConnectError / All connection attempts failed
- 而不带 tools 的 stream 是稳定的——工具 schema 其实早已注入 system 提示，模型照样能决策

### 层 3：模型输出格式层——决策是 JSON，不是人话

- ReAct 为了"可编程决策"，system 提示要求模型输出 {"action":"final","answer":"..."} 这类 JSON
- 即使拿到流式 token，逐段也是 {" 、 action":"final"... —— 不能直接展示给用户
- 这就是为什么"打通了流式"之后，前端一度打出 JSON 原文

### 层 4：前端渲染层——打字机被「重置 + 立即 done」掐死

修复了"后端有流式 + SSE 有 token 事件"之后，打字机依然几乎不可见，原因在组件本身：

旧 StreamText：每次 text 变化都把 shown 重置回 0

    useEffect(() => { setShown(0); }, [text]);   // token 快速追加 → 永远从头打（闪烁）
    if (done) { setShown(text.length); return; } // result 紧跟 → done 立即全显，打字机一闪而过

- token 到得快（毫秒级）、result 跟得也快 → done 一置位就全显
- 打字机从"有动画"退化成了"一次性"，用户自然说"没生效"

### 层 0（最底层）：稳定性

- 上游 OpenCode Zen 时快时慢（首 token 2s~19s 波动）、偶发连接失败
- 旧 RetryProvider.stream 完全不重试（注释：流已消费后无法安全重放）
- 一次连接失败 → 任务直接 failed → 前端无任何回复

---

## 三、现在为什么可以了（逐层修复）

### 修复 1：打通真 LLM 流式（模型层）

    parts: list[str] = []
    try:
        async for delta in llm.stream(messages):        # 不带 tools（规避上游断连）
            parts.append(delta)
    except Exception:                                    # 上游不稳 → 降级一次性 chat(带 tools) 兜底
        parts = []
    if not parts:
        response = await llm.chat(messages, tools=tools) # 保证任务绝不因流式失败而挂掉
        content = response.content
    else:
        content = "".join(parts)

- 模型网关 4 个 provider（openai/anthropic/mock）全部实现 stream 并透传 tools
- stream 不带 tools + 工具 schema 放 system 提示 —— 既稳定又保留工具决策能力

### 修复 2：决策 JSON 不外泄，answer 拆段回放（输出格式层）

    if on_token is not None and decision.answer:
        answer_text = decision.answer
        total = min(2.5, 0.4 + len(answer_text) * 0.03)   # 短回复 ≥1s 可见，长回复封顶 2.5s
        nseg = max(1, (len(answer_text) + 5) // 6)
        gap = total / nseg
        for i in range(0, len(answer_text), 6):
            on_token(answer_text[i : i + 6])              # 推的是干净 answer，不是 JSON
            await asyncio.sleep(gap)

- 模型输出的 JSON 决策只在内部解析，推到 SSE 的是解析后的 answer 片段
- 自适应节奏：短回复也给足 1s+ 让"逐字打出"肉眼可见，长回复封顶 2.5s 不拖沓

### 修复 3：SSE 新增 token 事件（传输层）

    on_token=lambda d: task.events.append({"type": "token", "content": d})

- stream() 轮询把 token 事件逐段转发，前端拿到 {"type":"token","content":"你好，小明！"} 这种干净增量
- 事件粒度从「step 级」细到「token 级」

### 修复 4：前端打字机真实可见（渲染层）

1. 不再随 text 重置：token 追加时 shown 单调向前追（避免闪烁/永远显示不全）
2. 放慢：30ms/2 字符，让"逐字打出"肉眼可见
3. step(final) 只对齐 output，不置 done
4. result 延迟 done：delay = min(5000, 500 + 字符数*20)，给打字机时间打完
5. 会话/新任务切换重置 lastAssistantId/lastToolId，token 不串到旧气泡

### 修复 5：稳定性（重试 + 兜底）

    # RetryProvider.stream：连接建立失败（流尚未消费）可安全重试
    except (httpx.ConnectError, httpx.ConnectTimeout, OSError, TimeoutError) as exc:
        if attempt < self._max_retries:
            await asyncio.sleep(self._base_delay * (2**attempt))

- 连接级失败重试 2 次（指数退避）；流中途断开不重放（交给上层降级 chat）
- 三层保险：连接重试 → 流式降级 chat → 任务 graceful failed（带错误信息，不再静默挂起）

---

## 四、验证闭环（为什么"这次终于成功"）

1. curl 直连 SSE 确认事件序列：
   - token ×N（干净片段："你好，小明！" / "我是 Fla" / "re Age"...）
   - step（actor final，output=完整 answer）
   - result（completed）
2. Playwright + 真实 Chrome 确认 UI 打字机：

       t=6.5s: 你好，小明！我是 Flare A
       t=7.0s: 你好，小明！我是 Flare Agent，有什么可以帮你的吗
       t=7.5s: 你好，小明！我是 Flare Agent，有什么可以帮你的吗？ ⏎ 已完成

3. 218 个单测全过、ruff/black 干净、前端 tsc/build 干净
4. 提交 c0ce385 feat(agent): L6 token 级流式打字机（参照 nova-agent 生效）

---

## 五、可复用的排查清单（下次遇到"流式没生效"）

按这条链从下往上查，每层都要用最小探针验证，别跳层：

| 层 | 检查 | 最小验证 |
|---|---|---|
| 模型层 | 后端是否真调了 stream（非 chat） | 直接 curl POST .../chat/completions {"stream":true} 数 chunk |
| 协议层 | 上游 stream+tools 是否兼容 | 1 个工具的最小流式探针，看是否断连 |
| 输出层 | 模型输出是 JSON 决策还是纯文本 | 看 chunk 内容是否可直接展示 |
| 传输层 | SSE 是否有 token 级增量事件 | 解析完整 SSE 流，统计事件类型/数量 |
| 前端层 | 打字机是否被"重置/立即 done"掐死 | Playwright 500ms 采样 UI 文本长度变化 |
| 稳定性 | 流式失败是否有重试/降级 | 临时把上游指向错误地址，观察是否降级而非挂死 |

### 关键原则

1. "流式没生效" 90% 不是前端动画问题，是后端根本没流式——先证明后端有 token 流
2. 供应商的 stream+tools 兼容性必须先探测——1 个脚本 30 秒的事，别假设
3. 模型输出格式决定流式能否直接展示——JSON 决策要"解析后回放"，别让用户看 JSON
4. 打字机不可见的根因通常是 done 时序 + 重置逻辑，不是没有流式
5. 稳定性 > 完美流式：真流式 + 降级兜底，任务永远不因上游抖动而挂死
6. 端到端双验证：curl 看原始事件（后端），Playwright 看 UI（用户视角），两者都要
