"""沙箱执行服务（M4：子进程 -> 容器 -> Kata/Firecracker 演进）。

导出统一 SandboxRunner 协议 + 开发/生产实现 + 按环境装配工厂。
    上层（工具/Agent/API）只依赖 SandboxRunner，不感知具体隔离实现。
"""

from __future__ import annotations

from flare_common.config import Settings
from sandbox.runner import (
    CodeResult,
    DockerSandbox,
    LocalProcessSandbox,
    SandboxConfig,
    SandboxError,
    SandboxRunner,
    SandboxUnavailableError,
)
from sandbox.sandbox_tools import build_sandbox_run_tool


def build_sandbox(settings: Settings) -> SandboxRunner:
    """按环境装配沙箱：prod 用容器（未就绪则 fail-fast），开发用本地子进程。"""
    if settings.env == "prod":
        return DockerSandbox()
    return LocalProcessSandbox()


__all__ = [
    "CodeResult",
    "DockerSandbox",
    "LocalProcessSandbox",
    "SandboxConfig",
    "SandboxError",
    "SandboxRunner",
    "SandboxUnavailableError",
    "build_sandbox",
    "build_sandbox_run_tool",
]
