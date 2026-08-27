"""沙箱执行器（M4）：Agent 安全执行代码/命令。

- LocalProcessSandbox：开发默认（asyncio 子进程 + 超时 + 输出截断 + POSIX 内存上限）；
- DockerSandbox：生产占位（容器隔离，未就绪 fail-fast，不静默降级到本地进程）。

真理：沙箱是"可执行工具的 Agent"的安全底线——
  1. 超时（防死循环）、输出上限（防刷爆上下文）、资源上限（防拖垮宿主）是底线；
  2. 开发用子进程够跑单测；生产必须容器/Kata 隔离 + 网络隔离（M5）；
  3. 不可用时必须 fail-fast，绝不"悄悄在宿主机裸跑"。
"""

from __future__ import annotations

import asyncio
import contextlib
import sys
import time
from dataclasses import dataclass
from typing import Protocol

from flare_common.errors import FlareError

_IS_POSIX = sys.platform != "win32"


class SandboxError(FlareError):
    code = "SANDBOX_ERROR"
    status_code = 500


class SandboxUnavailableError(FlareError):
    code = "SANDBOX_UNAVAILABLE"
    status_code = 503


@dataclass
class CodeResult:
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_s: float


@dataclass
class SandboxConfig:
    timeout_s: float = 10.0
    max_output_chars: int = 4000
    max_memory_mb: int = 256
    interpreter: str = ""  # 空 = 当前 Python 解释器


class SandboxRunner(Protocol):
    async def run(
        self, code: str, *, language: str = "python", stdin: str | None = None
    ) -> CodeResult: ...


def _cap(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n...(截断，共 {len(text)} 字符)"


def _limit_memory(memory_mb: int) -> None:
    """POSIX 子进程地址空间上限（Windows 无 rlimit，跳过）。"""
    import resource

    limit = memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


class LocalProcessSandbox:
    """开发沙箱：本地子进程 + 超时 + 输出截断 + 内存上限（POSIX）。"""

    def __init__(self, config: SandboxConfig | None = None) -> None:
        self._config = config or SandboxConfig()

    async def run(
        self, code: str, *, language: str = "python", stdin: str | None = None
    ) -> CodeResult:
        if language != "python":
            raise SandboxError(f"暂不支持语言: {language}（当前仅 python）")
        interpreter = self._config.interpreter or sys.executable
        start = time.monotonic()
        kwargs: dict = {
            "stdin": asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.PIPE,
        }
        if _IS_POSIX:
            kwargs["preexec_fn"] = lambda: _limit_memory(self._config.max_memory_mb)
        try:
            proc = await asyncio.create_subprocess_exec(interpreter, "-c", code, **kwargs)
        except OSError as exc:
            return CodeResult(
                ok=False,
                exit_code=-1,
                stdout="",
                stderr=str(exc),
                timed_out=False,
                duration_s=time.monotonic() - start,
            )
        timed_out = False
        try:
            out, err = await asyncio.wait_for(
                proc.communicate(stdin.encode("utf-8") if stdin is not None else None),
                timeout=self._config.timeout_s,
            )
        except TimeoutError:
            timed_out = True
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            out, err = await proc.communicate()
        duration = time.monotonic() - start
        stdout = _cap((out or b"").decode("utf-8", errors="replace"), self._config.max_output_chars)
        stderr = _cap((err or b"").decode("utf-8", errors="replace"), self._config.max_output_chars)
        return CodeResult(
            ok=(proc.returncode == 0 and not timed_out),
            exit_code=proc.returncode or 0,
            stdout=stdout,
            stderr=stderr,
            timed_out=timed_out,
            duration_s=round(duration, 3),
        )


class DockerSandbox:
    """生产沙箱占位：容器隔离（M5 起：--network=none + 内存/CPU 限制 + Kata/Firecracker）。

    未检测到 docker 或未接入时 fail-fast 抛 SandboxUnavailableError——
    生产绝不静默降级到宿主机裸跑。
    """

    def __init__(self, image: str = "python:3.12-slim", timeout_s: float = 15.0) -> None:
        self._image = image
        self._timeout_s = timeout_s

    async def run(
        self, code: str, *, language: str = "python", stdin: str | None = None
    ) -> CodeResult:
        import shutil

        if shutil.which("docker") is None:
            raise SandboxUnavailableError("未检测到 docker，生产沙箱不可用")
        raise SandboxUnavailableError(f"docker 沙箱执行（{self._image}）待 M5 接入，当前 fail-fast")
