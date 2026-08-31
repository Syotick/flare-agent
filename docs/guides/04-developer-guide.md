# 04 · 二次开发指南

> 目标读者：要在这个项目上改代码、加功能的人。
> 读完本篇你会：**能加一个新工具、加一个新 API、跑测试、跑前端、用 CLI 调试**。

---

## 0. 开发环境

```bash
# Python 3.12，建议 conda/venv
pip install -r requirements.txt -r requirements-dev.txt

# 以可编辑模式安装（这样 uvicorn / pytest 能在任意目录找到 services/ 下的包）
pip install -e .
```

后端改完**重启 uvicorn** 生效；前端改完 **`npm run build`** 后刷新页面即可（dist 由后端实时挂载，无需重启后端）。

---

## 1. 加一个工具（10 分钟上手）

工具 = 名称 + 描述 + 参数 Schema + 异步函数，集中在 **ToolRegistry** 注册。最快路径：加进 `services/tools_gateway/builtin.py`。

### 1.1 写工具函数

打开 `services/tools_gateway/builtin.py`，加一个"查当前时间"的工具：

```python
from datetime import datetime

async def _tool_now(_tz: str = "local") -> ToolResult:
    """返回当前时间。"""
    if _tz == "utc":
        return ToolResult(ok=True, content=datetime.utcnow().isoformat() + "Z")
    return ToolResult(ok=True, content=datetime.now().isoformat())
```

### 1.2 注册它

在 `create_default_registry()` 里 `register(...)`：

```python
registry.register(
    Tool(
        name="now",
        description="获取当前时间（本地或 UTC）。",
        parameters={
            "type": "object",
            "properties": {"tz": {"type": "string", "enum": ["local", "utc"], "default": "local"}},
        },
        func=_tool_now,
        permission=PERMISSION_READ,  # 只读：不需要审批
    )
)
```

> 权限分级：`read`（免审批）/ `write`（可审批）/ `destructive`（默认强制审批）。工具函数返回 `ToolResult(ok, content, error_code, artifacts)`。

### 1.3 测试它

在 `tests/unit/` 建 `test_now_tool.py`：

```python
import asyncio

def test_now_tool_runs():
    from tools_gateway.builtin import create_default_registry

    reg = create_default_registry()
    res = asyncio.run(reg.execute("now"))
    assert res.ok
    assert "T" in res.content  # ISO 时间含 T
```

跑它：

```bash
pytest tests/unit/test_now_tool.py -q
```

模型就会在需要"当前时间"时自动用这个工具。

---

## 2. 加一个 API

路由都在 `services/agent_runtime/routes/`。以加 `GET /v1/hello` 为例：

```python
# routes/hello.py
from fastapi import APIRouter

router = APIRouter(prefix="/v1", tags=["hello"])

@router.get("/hello")
async def hello(name: str = "world"):
    return {"message": f"hello {name}"}
```

在 `app.py` 的 create_app 里注册：

```python
from agent_runtime.routes.hello import router as hello_router
app.include_router(hello_router)
```

重启后：`curl http://127.0.0.1:8000/v1/hello?name=flare`。

> 错误契约：抛 `flare_common.errors.FlareError`（子类带 `code` + `status_code`），统一返回 `{code, message, request_id}`，前端 `api.ts` 的 `json()` 会解析。

---

## 3. 跑测试

项目有 **265 个测试**，覆盖单元 / API / 工作区工具全链路：

```bash
# 全部
pytest -q

# 单个模块
pytest tests/unit/test_tasks_api.py -q
pytest tests/unit/test_workspace_tools.py -q

# 带输出
pytest tests/unit/test_workspace_tools.py::test_bash -q
```

测试配置在 `pyproject.toml`（`testpaths`、`asyncio_mode=auto`、`pythonpath=["services", "."]`）。测试里常用 **mock 模型**（`model_gateway.mock.MockModelProvider`）跑通流程，不碰真实 API。

---

## 4. 前端开发

`services/web/` 是 React 18 + Vite + Tailwind v4：

```bash
cd services/web
npm install

# 方式 A：改完直接 build，后端挂载刷新即看
npm run build

# 方式 B：Vite dev server（后端仍提供 /v1 API，前端走代理）
npm run dev
```

关键入口：
- `src/App.tsx`：应用骨架 + 状态（会话/工作区/模型/权限模式）
- `src/components/ChatView.tsx`：对话渲染（Markdown、气泡、工具卡片、审批卡）
- `src/components/Composer.tsx`：输入框 + 权限模式/模型选择
- `src/components/Sidebar.tsx`：会话/工作区管理
- `src/api.ts`：所有后端 API 封装（一个函数一个接口）
- `src/styles.css`：flare 主题（渐变/光晕/动画）

---

## 5. CLI

项目内置 `flare` 命令（`services/flare_cli/main.py`），终端里调试很方便：

```bash
flare --help
```

（支持从终端发任务、查状态等；开发时可直接 `python -m flare_cli.main ...` 调试）

---

## 6. 代码规范

- **格式**：`black`（line-length 100）+ `ruff`（配置在 `pyproject.toml`）
- 提交前：
  ```bash
  black services tests
  ruff check services tests
  pytest -q
  ```
- **提交信息**：Conventional Commits，如 `feat(tools): add now tool` / `fix(web): 布局自适应`

---

## 7. 踩坑提示

| 坑 | 解决 |
| --- | --- |
| 改了后端没生效 | 重启 uvicorn（Python 改动要重启） |
| 改了前端没生效 | `npm run build` 后**硬刷新**（缓存） |
| 测试连真实 API | 测试默认 mock 模型 + 内存/临时存储，别担心 |
| 加工具模型不会用 | 描述写清楚 + 参数 Schema 给枚举/示例；模型靠 description 学会调用 |
| 中文在控制台乱码 | Windows 控制台 GBK：用 UTF-8 输出或 `PYTHONIOENCODING=utf-8` |

---

## 下一步

→ [05 · 进阶主题](05-advanced.md)：模型配置 / 权限策略 / 工作区代码能力 / RAG / 记忆 / 多 Agent / MCP / 技能 / 运维。