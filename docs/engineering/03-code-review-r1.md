# Flare Agent · 首轮代码审查记录（Round 1）

> 版本：v1.0 ｜ 日期：2026-08-27 ｜ 状态：approved（全部处置完成）
> 审查范围：services/ + tests/（当时约 285 行 Python）与配套配置
> 处置规则：不冲突的直接修复；需拍板的（A2 工具接口、L3 配置严格度）已按推荐项实施，用户可否决

---

## 1. 处置汇总

| 编号 | 意见 | 结论 | 处置 |
| --- | --- | --- | --- |
| D1 | 裸顶层包名 + PYTHONPATH 依赖 | 成立 | ✅ common→flare_common（git mv），可独立安装（pip install -e . + build-system） |
| D2 | 无 app 工厂、import 副作用 | 成立 | ✅ create_app() 工厂 + settings 注入（app.py / main.py 拆分） |
| D3 | CORS 硬编码 | 成立 | ✅ cors_origins 进 Settings（dev=["*"]，生产 JSON 数组） |
| D4 | 异常类耦合、缺跨进程契约 | 部分成立 | ✅ 随 A4 建立稳定错误响应结构；**跨进程传输留待服务拆分时** |
| Settings | 全局配置袋生长点 | 预警 | ⏳ M3 复查（<200 行且单一职责，否则拆子模型） |
| Registry | 职责膨胀风险 | 预警 | ✅ docstring 立边界：注册/查询/执行，横切能力独立分层；M3 复查 |
| C1 | 版本号多来源 | 成立 | ✅ 单一事实来源：importlib.metadata.version("flare-agent") + 一处回退常量 |
| C2 | 测试重复构造 | 成立 | ✅ pytest fixture |
| A1 | Schema 只声明不校验 | 成立 | ✅ jsonschema 校验，非法参数抛 ValidationError(422) |
| A2 | 接口 sync str→str、契约说谎 | 成立 | ✅ **async + ToolResult(ok/content/error_code/artifacts)**；required 缺失校验层报错 |
| A3 | 模型供应商无抽象 | 成立 | ✅ ModelProvider Protocol(chat/stream+usage) + MockModelProvider |
| A4 | 错误码没接 HTTP | 成立 | ✅ FlareError/通用异常 handler -> {code,message,request_id} + 响应形状测试 |
| A5 | telemetry 占位 | 可接受 | 保留（M5 接导出器） |
| L1 | 文档/代码失衡 | 采纳 | ✅ M2 以"可运行端到端回路"为硬目标，文档增速低于代码增速 |
| L2 | demo 优先定型接口 | 成立 | ✅ = A1/A2 根因，已随修复 |
| L3 | extra=ignore 掩盖配置错误 | 成立 | ✅ extra="forbid"（拼错即启动报错，fail-fast） |
| L4 | 死类残留 | 判断 | RateLimitError 保留（错误码契约，M5 限流使用）；telemetry 保留（审查同意） |
| L5 | 测试风格不统一 | 成立 | ✅ 顶部 import + 真实 async 工具函数 |

## 2. 核心复查清单（下轮核对）

| # | 落实标准 | 状态 |
| --- | --- | --- |
| 1 | ToolResult / async / schema 校验 + 非法参数测试 | ✅ |
| 2 | /version 与 pyproject 同源，无硬编码 | ✅ |
| 3 | create_app() 工厂，端点注入 settings | ✅ |
| 4 | cors_origins 进 settings | ✅ |
| 5 | extra=forbid | ✅ |
| 6 | LangGraph 图开工前有 ModelProvider 接口 + mock | ✅ |
| 7 | FlareError 接 HTTP + 响应形状测试 | ✅ |
| 8 | M2 有可运行的端到端回路 | 🔨 M2-4b 进行中 |

## 3. 待办（后续轮次）

- D4 跨进程错误契约：服务拆分时定义 wire 格式（错误码/错误对象序列化）
- Settings 按域拆子模型（DB/ObjectStore/Model）：M3 复查触发
- Registry 横切能力（权限/限流/审计/审批）独立分层：M3
- Starlette TestClient/httpx 弃用告警：升级适配
