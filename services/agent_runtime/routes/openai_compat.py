"""OpenAI 兼容 REST API（F9.3）：让 OpenAI SDK / LiteLLM / curl 直接调用 Flare Agent。

- POST /v1/chat/completions：标准 Chat Completions 契约（含 stream=true 的 SSE 分块）
- GET  /v1/models：模型列表（OpenAI 兼容客户端启动时会先调用）

设计（对接"多 Agent 并行 + 工具生态"后的接入形态）：
- 复用 TaskManager：任务照常登记/可观测/可查（与 /v1/tasks 同一套存储与指标）；
  非流式请求同步等待任务完成（轮询 store），stream=true 时结果就绪后按词回放
- 消息→任务：取最后一个 user 消息内容作为 task_input（工具调用发生在 Agent 内部）
- 模型名：model 参数回显（实际推理模型由 FLARE_MODEL_NAME 决定，MVP 不强制匹配）
- 认证：FLARE_API_KEY 配置后要求 Authorization: Bearer（未配置=开放）
- 错误：OpenAI 风格 {"error": {"message","type","param","code"}} + 正确 HTTP 状态

真理：OpenAI 兼容 API 是"生态接入"的事实标准——任何 OpenAI SDK 客户端零改造成本接入，
CLI/LiteLLM/第三方编排器都能把 Flare 当模型端点用。这是把 Agent 能力"产品化"的入口。
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from agent_runtime.tasks import TaskManager
from flare_common import metrics

WAIT_TIMEOUT = 60.0  # 非流式请求等待任务完成的秒数上限
POLL_INTERVAL = 0.05


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "flare-agent"
    messages: list[ChatMessage] = Field(min_length=1)
    stream: bool = False
    max_tokens: int | None = None  # 接受但由模型层决定（MVP：无 token 预算侧）
    max_steps: int = Field(default=5, ge=1, le=50)  # 扩展参数：Agent 步骤预算
    temperature: float | None = None


class OpenAICompatError(Exception):
    """OpenAI 兼容错误：扁平 {"error": {...}} 响应体（不经过 FastAPI 的 detail 包装）。"""

    def __init__(
        self, status: int, message: str, code: str, *, etype: str = "invalid_request_error"
    ) -> None:
        super().__init__(message)
        self.status = status
        self.error_body = {"message": message, "type": etype, "param": None, "code": code}

    def to_response(self) -> JSONResponse:
        return JSONResponse(status_code=self.status, content={"error": self.error_body})


def _extract_task_input(messages: list[ChatMessage]) -> str:
    """取最后一个 user 消息内容作为任务输入；无 user 消息 -> 400（OpenAI 风格错误）。"""
    for m in reversed(messages):
        if m.role == "user":
            return m.content
    raise OpenAICompatError(400, "messages 中缺少 user 消息", "missing_user_message")


def _openai_error(status: int, message: str, code: str) -> OpenAICompatError:
    return OpenAICompatError(status, message, code)


def _require_api_key(request: Request, api_key: str) -> None:
    """FLARE_API_KEY 配置后校验 Authorization: Bearer（未配置=开放）。"""
    if not api_key:
        return
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {api_key}":
        raise OpenAICompatError(
            401, "无效或缺失的 API Key", "invalid_api_key", etype="authentication_error"
        )


async def _wait_done(manager: TaskManager, task_id: str) -> dict[str, Any]:
    """轮询任务到终态（或超时）；返回 task.to_dict()。"""
    deadline = time.monotonic() + WAIT_TIMEOUT
    while time.monotonic() < deadline:
        task = await manager.get(task_id)
        if task is not None and task.done:
            return task.to_dict()
        await asyncio.sleep(POLL_INTERVAL)
    raise _openai_error(504, f"任务 {task_id} 等待超时", "task_timeout")


def _task_output(result: dict[str, Any]) -> str:
    """从 task.to_dict() 里取最终输出文本（result.output，带兜底）。"""
    inner = result.get("result") or {}
    if isinstance(inner, dict):
        return str(inner.get("output") or "")
    return str(inner or "")


def _completion_object(task_id: str, model: str, content: str, task_input: str) -> dict[str, Any]:
    """组装 OpenAI chat.completion 响应对象。"""
    return {
        "id": f"chatcmpl-{task_id}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": len(task_input),
            "completion_tokens": len(content),
            "total_tokens": len(task_input) + len(content),
        },
    }


def _sse_chunk(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _chunk_object(
    task_id: str, model: str, content: str, finish_reason: str | None
) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-{task_id}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"content": content} if content else {},
                "finish_reason": finish_reason,
            }
        ],
    }


async def _stream_result(manager: TaskManager, task_id: str, model: str) -> AsyncIterator[str]:
    """任务完成前先阻塞等待，随后按词回放结果（OpenAI chunk 格式 + [DONE]）。

    MVP 语义：Agent 工具调用在服务端内部完成，stream 只回放最终输出；
    与真实 token 流形状一致，客户端（openai SDK/CLI）无需特殊处理。
    """
    try:
        result = await _wait_done(manager, task_id)
    except OpenAICompatError:
        yield _sse_chunk(_chunk_object(task_id, model, "", "error"))
        yield "data: [DONE]\n\n"
        return
    status = result.get("status")
    output = _task_output(result)
    if status != "completed":
        output = f"[{status}] {output}".strip()
    # 首块带 role 提示（OpenAI 客户端约定）
    yield _sse_chunk(
        {
            "id": f"chatcmpl-{task_id}",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}
            ],
        }
    )
    for word in output.split(" "):
        yield _sse_chunk(_chunk_object(task_id, model, word + " ", None))
    yield _sse_chunk(_chunk_object(task_id, model, "", "stop"))
    yield "data: [DONE]\n\n"


def build_openai_router(manager: TaskManager, *, api_key: str = "") -> APIRouter:
    """构建 OpenAI 兼容路由（F9.3）。

    - manager: TaskManager（任务登记/执行/查询）
    - api_key: FLARE_API_KEY（空=开放；非空=要求 Bearer）
    """
    router = APIRouter(prefix="/v1", tags=["openai"])

    @router.get("/models")
    async def list_models(request: Request):
        try:
            _require_api_key(request, api_key)
        except OpenAICompatError as exc:
            return exc.to_response()
        return {
            "object": "list",
            "data": [
                {
                    "id": "flare-agent",
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "flare",
                }
            ],
        }

    @router.post("/chat/completions")
    async def chat_completions(request: Request, body: ChatCompletionRequest):
        try:
            _require_api_key(request, api_key)
            task_input = _extract_task_input(body.messages)
        except OpenAICompatError as exc:
            return exc.to_response()
        task = await manager.create(task_input, max_steps=body.max_steps)
        if body.stream:
            return StreamingResponse(
                _stream_result(manager, task.task_id, body.model),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
            )
        started = time.monotonic()
        try:
            result = await _wait_done(manager, task.task_id)
            status = result.get("status")
            output = _task_output(result)
            if status != "completed":
                raise _openai_error(
                    500, f"Agent 任务未完成（{status}）: {output[:200]}", "agent_failed"
                )
        except OpenAICompatError as exc:
            return exc.to_response()
        metrics.observe_task(
            "succeeded" if result.get("status") == "completed" else "errored",
            time.monotonic() - started,
        )
        return _completion_object(task.task_id, body.model, output, task_input)

    return router
