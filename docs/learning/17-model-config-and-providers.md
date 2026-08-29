> 版本：v1.0 ｜ 日期：2026-08-29 ｜ 状态：draft ｜ 负责人：flare

# 模型配置与供应商接入（M4 wiring 修复 + 控制台「模型」页）

> 配套：learning/10 讲模型网关内部（provider/function-calling/重试）；本篇讲
> **怎么把真实模型接进产品**：配置的持久化、生效优先级、UI 闭环、安全边界。

## 一、背景：配置了 openai 却不生效（真 bug）

M4 交付时 `build_provider(settings)` 工厂是写好的，但 **create_app 构造 TaskManager
从未传 llm** —— `TaskManager.__init__` 默认 `llm or MockModelProvider()`，于是真实服务
**永远跑 mock**，用户填了 FLARE_MODEL_API_KEY 也白填。lesson：**能力层做好了不代表
运行链路接上了**——"一个能力 = 一个 REST 端点 + 一个前端视图 + 一条 wiring 链路"，
三者缺一就是死代码（前端入口闭环的原则同样适用于后端装配）。

修复：create_app 里 `llm = build_provider(model_store.to_settings())` 传入 TaskManager。

## 二、配置优先级与持久化（ModelConfigStore）

`services/agent_runtime/model_config.py`：

- 生效优先级：**真实环境变量 > 本地 JSON(data/model_config.json) > pydantic(.env/默认)**。
  生产用 env/K8s Secret 注入即自动压制 UI 保存的本地配置——UI 只是本地开发/自托管便利，
  不污染生产。
- `_env_value` 读的是 **FLARE_MODEL_\* 全名**（映射字段 provider→model_provider），
  .env 文件属于 pydantic 解析层，不在此列。
- 落盘写临时文件后 os.replace（原子）；chmod 0600（Windows 为 no-op）。

## 三、脱敏契约（安全边界）

- GET /v1/settings/model 只回 provider/base_url/model_name/has_api_key/api_key_source，
  **api_key 明文永不回传浏览器**；
- key 只在服务端文件里；PUT 时 api_key 空串 = 清除，前端"留空=保持不变"靠"不发该字段"
  区分，另有显式「清除已存 Key」按钮，避免误清。

## 四、热生效（set_llm）

保存配置后 route 调 `task_manager.set_llm(build_provider(store.to_settings()))`，
旧 provider close() 释放 httpx 连接。TaskManager 每次 _execute 用当前 _llm 建图，
故**对新建任务生效，正在运行的任务不受影响**（UI 明示）。

## 五、连通性测试

POST /v1/settings/model/test：body 可带临时覆盖（不保存）。mock 直返 ok；
openai 协议 GET {base}/models 验证端点+鉴权，返回检测到的模型列表或明确错误
（401 鉴权失败 / ConnectError 不可达 / HTTP 状态）。

## 六、供应商预设

presets 内置 OpenAI / DeepSeek / 通义百炼 / 硅基流动 / Ollama / vLLM / 自定义——
同 OpenAI /chat/completions 协议，只换 base_url + model_name。

## 七、踩坑记录

- Settings 属性名是 model_provider 而本地字段是 provider：getattr 必须走映射表；
- env 名是 FLARE_MODEL_PROVIDER 而非 FLARE_PROVIDER（拼字段映射的 upper，不是字段本身）；
- store 默认 path 必须从 settings.model_config_path 取，否则测试 tmp 隔离失效、
  真实文件被测试写坏（最初测试全部串读同 repo 文件）；
- 写 TSX 组件内容时禁用反引号模板串（会截断外层模板字面量）——用字符串拼接。

## 八、验收清单

- [x] create_app 真正装配 build_provider（M4 wiring 修复，不再是死 mock）
- [x] ModelConfigStore：env > JSON > settings 优先级 + 原子落盘 + 0600
- [x] GET/PUT/presets/test 四端点，脱敏契约（key 永不回显）
- [x] 保存热生效（set_llm，新建任务生效）
- [x] 控制台「模型」视图（预设下拉/表单/password key/保存/测试/清除 key）
- [x] 全量 211 测试全绿 + ruff/black + tsc/vite + 真实服务器冒烟
  （保存→脱敏→落盘→mock/openai 测试→清除；已还原干净 mock 状态）
