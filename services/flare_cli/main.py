"""flare 命令行（F9.2）：chat / tasks / task / models。

用法示例（默认连本地 http://127.0.0.1:8000，可 --url / FLARE_URL 覆盖）：
    python -m flare_cli chat "帮我把周报拆成三点"          # 流式
    python -m flare_cli chat "..." --json --no-stream      # 非流式 JSON
    python -m flare_cli tasks
    python -m flare_cli task <task_id>
    python -m flare_cli models
认证：--api-key 或 FLARE_API_KEY（对应 FLARE_API_KEY 服务端配置）。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

import httpx

from flare_cli.client import FlareClient


def _print_error(exc: httpx.HTTPStatusError) -> None:
    try:
        body = exc.response.json()
        msg = (body.get("error") or {}).get("message") or str(exc)
    except ValueError:
        msg = str(exc)
    print(f"错误: {msg}", file=sys.stderr)
    print(f"HTTP {exc.response.status_code}", file=sys.stderr)


async def _dispatch(args: argparse.Namespace) -> int:
    client = FlareClient(args.url, api_key=args.api_key)
    try:
        if args.cmd == "chat":
            if args.json or args.no_stream:
                resp = await client.chat(args.prompt, model=args.model, max_steps=args.max_steps)
                if args.json:
                    print(json.dumps(resp, ensure_ascii=False, indent=2))
                else:
                    content = resp["choices"][0]["message"]["content"]
                    print(content)
            else:
                sys.stdout.write("> ")
                sys.stdout.flush()
                async for delta in client.chat_stream(
                    args.prompt, model=args.model, max_steps=args.max_steps
                ):
                    sys.stdout.write(delta)
                    sys.stdout.flush()
                print()
            return 0

        if args.cmd == "tasks":
            tasks = await client.list_tasks()
            if not tasks:
                print("（无任务）")
                return 0
            for t in tasks:
                snippet = t["task_input"][:60]
                print(f"{t['task_id']}  {t['status']:<16} steps={t['step_count']}  {snippet}")
            return 0

        if args.cmd == "task":
            if args.stream:
                async for line in client.stream_task(args.task_id):
                    print(line)
                return 0
            t = await client.get_task(args.task_id)
            print(json.dumps(t, ensure_ascii=False, indent=2))
            return 0

        if args.cmd == "models":
            for m in await client.list_models():
                print(f"{m['id']}  owned_by={m['owned_by']}")
            return 0

    except httpx.HTTPStatusError as exc:
        _print_error(exc)
        return 1
    except httpx.HTTPError as exc:
        print(f"连接失败: {exc}", file=sys.stderr)
        return 1
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flare",
        description="Flare Agent CLI（F9.2）——OpenAI 兼容端点 + 任务 API 瘦客户端",
    )
    parser.add_argument("--url", default=os.environ.get("FLARE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--api-key", default=os.environ.get("FLARE_API_KEY", ""))
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_chat = sub.add_parser("chat", help="提交对话任务（默认流式输出）")
    p_chat.add_argument("prompt", help="任务描述")
    p_chat.add_argument("--model", default="flare-agent")
    p_chat.add_argument("--max-steps", type=int, default=5)
    p_chat.add_argument("--no-stream", action="store_true", help="非流式（拿到完整结果再输出）")

    sub.add_parser("tasks", help="最近任务列表")

    p_task = sub.add_parser("task", help="任务详情")
    p_task.add_argument("task_id")
    p_task.add_argument("--stream", action="store_true", help="SSE 实时流")

    sub.add_parser("models", help="模型列表")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(_dispatch(args))


if __name__ == "__main__":
    raise SystemExit(main())
