# 01 · 快速开始（5 分钟跑通）

> 目标读者：有 Python / Node 基础，想把 Flare Agent 跑起来的人。
> 读完本篇你会：**启动后端 + 前端、发第一个任务、接上真实模型、建第一个工作区**。

---

## 0. 环境要求

| 依赖 | 版本 | 说明 |
| --- | --- | --- |
| Python | 3.12 | 后端运行时 |
| Node | 18+ | 前端构建 |
| Git Bash | Windows 需要 | Agent 跑命令用的 shell（Linux/macOS 自带 bash） |

> 确认环境：`python --version`、`node --version`。

## 1. 安装依赖

在项目根目录：

```bash
pip install -r requirements.txt
```

> 建议先建虚拟环境（conda / venv 均可）。项目依赖都列在 `requirements.txt`，没有隐藏依赖。

## 2. 构建前端

前端构建产物由后端直接挂载，**构建一次即可**，无需再开 dev server：

```bash
cd services/web
npm install
npm run build
cd ../..
```

## 3. 启动后端

```bash
python -m uvicorn agent_runtime.main:app --host 127.0.0.1 --port 8000
```

看到 `Uvicorn running on http://127.0.0.1:8000` 就成功了。

打开 **http://127.0.0.1:8000**，你会看到完整控制台：左侧工作区 + 会话列表 + 导航，中间是对话区。

## 4. 发第一个任务

刚启动时模型是 **mock**（不需要任何 API Key 就能跑通全流程）。发一个任务：

```bash
curl -X POST http://127.0.0.1:8000/v1/tasks \
  -H 'Content-Type: application/json' \
  -d '{"task_input":"你好，帮我打个招呼"}'
```

返回（202）：

```json
{"task_id":"a1b2c3d4e5f6","thread_id":"...","status":"running","workspace_id":"default"}
```

用 `task_id` 看实时流（SSE，一步步推事件）：

```bash
curl -N http://127.0.0.1:8000/v1/tasks/a1b2c3d4e5f6/stream
```

或者直接**在网页里发**——你会看到打字机式回复和工具调用轨迹。

## 5. 接入真实模型（30 秒）

mock 只是跑通流程，要真正对话请配模型。两种方式：

### 方式 A：网页「模型」页（推荐）

1. 左侧导航点 **模型**
2. 选一个预设（DeepSeek / 通义百炼 / SiliconFlow / Ollama…），填 Base URL、Model Name、API Key
3. 点「保存」——热生效，新建任务即用新模型

### 方式 B：`.env` 文件

项目根建 `.env`（所有配置项都是 `FLARE_` 前缀环境变量，见 `services/flare_common/config.py`）：

```bash
FLARE_MODEL_PROVIDER=openai
FLARE_MODEL_BASE_URL=https://api.deepseek.com/v1
FLARE_MODEL_NAME=deepseek-chat
FLARE_MODEL_API_KEY=sk-你的key
```

重启后端生效。支持的 provider：`mock` / `openai`（兼容 DeepSeek/通义/vLLM/Ollama…）/ `anthropic`（Claude）。

## 6. 建第一个工作区（让 Agent 真正干活）

工作区 = 服务器上的一个**真实目录**，Agent 可以在里面读/写/搜/跑命令：

1. 左侧顶部点工作区按钮 → 「添加工作区…」
2. 在目录浏览器里选一个目录（比如放了个项目的文件夹），点「选择此文件夹作为工作区」
3. 在对话框里说："读一下这个项目的 README，总结它做什么"

Agent 会真的用 `read` 打开文件、`glob/grep` 找代码，最后给你一份 Markdown 总结。

想试试写代码 + 跑命令，把权限模式切到「⚡ 无限制」（Composer 顶部第一个 chip），然后说 "写个 hello.py 并运行"。

## 常见问题

| 现象 | 解决 |
| --- | --- |
| 8000 端口被占用 | 换端口：`--port 8001` |
| 打开网页只有 API 没有界面 | 前端没构建：回到第 2 步 `npm run build` |
| Agent 回复是"echo: ..." | 模型是 mock：配真实模型（第 5 步） |
| 模型连不上 / 401 | 检查 Base URL、API Key；DeepSeek 用 `https://api.deepseek.com/v1`，通义百炼用 `compatible-mode` 地址 |
| 想跑命令但提示要审批 | 默认「批准」模式：审批卡片里点批准；或切「无限制」 |

## 下一步

→ [02 · 核心概念](02-core-concepts.md)：任务 / 线程 / SSE 流式 / 工作区 / 工具 / 审批到底怎么工作。