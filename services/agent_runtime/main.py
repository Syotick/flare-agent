"""Agent Runtime 入口：uvicorn agent_runtime.main:app。"""

from agent_runtime.app import create_app

app = create_app()
