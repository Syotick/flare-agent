"""工作区工具集（对标 DSH read/write/edit/glob/grep + bash）。

核心：工具闭包绑定工作区根目录 cwd（TaskManager.task_view 每任务构建，
闭包内 observed 观察状态随任务生命周期、跨任务隔离）。

- 路径解析：相对路径 -> 基于 cwd（工作区内）；绝对路径允许（只读安全）；
  write/edit 目标不在 cwd 内 -> 拒绝（OUT_OF_BOUNDS）。
- read 前置策略（对标 DSH fs-observation-policy）：覆盖已存在文件前必须先 read；
  edit 需先 read 且文件自 read 后未变更（size+mtime 版本 CAS），防盲目覆盖。
- bash：每次全新 Git Bash 子进程（无 shell 状态），cwd 默认工作区，
  超时/输出上限/环境清理（NO_COLOR TERM=dumb PAGER=cat GIT_PAGER=cat）。
"""

from __future__ import annotations

import asyncio
import contextlib
import glob as pyglob
import os
import re
from pathlib import Path

from tools_gateway.registry import (
    PERMISSION_DESTRUCTIVE,
    PERMISSION_READ,
    PERMISSION_WRITE,
    Tool,
    ToolResult,
)

MAX_READ_LINES = 2000
MAX_GLOB = 100
MAX_GREP_MATCHES = 250
MAX_GREP_LINE_BYTES = 2000
BASH_MAX_OUTPUT = 64 * 1024
BASH_DEFAULT_TIMEOUT = 30.0
BASH_MAX_TIMEOUT = 120.0

_SKIP_DIRS = {
    ".git",
    ".svn",
    ".hg",
    ".bzr",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".next",
    ".idea",
}
_SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pyc",
    ".so",
    ".dll",
    ".exe",
    ".zip",
    ".tar",
    ".gz",
    ".bin",
}


def _resolve(cwd: str, file_path: str) -> Path:
    p = Path(file_path)
    return p if p.is_absolute() else Path(cwd) / p


def _in_workspace(cwd: str, path: Path) -> bool:
    try:
        path.resolve().relative_to(Path(cwd).resolve())
        return True
    except ValueError:
        return False


def _read_version(path: Path) -> tuple[int, int] | None:
    try:
        st = path.stat()
        return (st.st_size, st.st_mtime_ns)
    except OSError:
        return None


def _atomic_write(path: Path, content: str) -> None:
    """原子写：临时文件 + rename（对标 DSH LocalFileSystem.writeText）。"""
    tmp = path.with_name(path.name + ".flare.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def _cap(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n...(截断，共 {len(text)} 字符)"


def _find_bash() -> str:
    """定位 Git Bash：FLARE_SHELL 覆盖 > PATH 的 bash > Windows 常见安装路径。"""
    candidates = [os.environ.get("FLARE_SHELL") or "", "bash"]
    candidates += [
        "C:/Program Files/Git/bin/bash.exe",
        "C:/Program Files (x86)/Git/bin/bash.exe",
    ]
    for cand in candidates:
        if not cand:
            continue
        if os.path.isabs(cand):
            if os.path.exists(cand):
                return cand
        else:
            for d in os.environ.get("PATH", "").split(os.pathsep):
                if d and os.path.exists(os.path.join(d, cand)):
                    return os.path.join(d, cand)
    return "bash"  # 兜底：找不到也明确报错，不静默


# ---------------------------------------------------------------------------
# 文件工具（read / write / edit / glob / grep）
# ---------------------------------------------------------------------------


def _build_read(cwd: str, observed: dict) -> Tool:
    async def _read(file_path: str, offset: int = 1, limit: int = MAX_READ_LINES) -> ToolResult:
        path = _resolve(cwd, file_path)
        if not path.is_file():
            return ToolResult(ok=False, error_code="FILE_NOT_FOUND", content=f"文件不存在: {path}")
        offset = max(1, int(offset))
        limit = max(1, min(int(limit), MAX_READ_LINES))
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            return ToolResult(ok=False, error_code="NOT_TEXT", content=f"不是 UTF-8 文本: {path}")
        except OSError as exc:
            return ToolResult(ok=False, error_code="READ_ERROR", content=str(exc))
        total = len(lines)
        observed[str(path.resolve())] = _read_version(path)
        picked = lines[offset - 1 : offset - 1 + limit]
        rendered = "\n".join(f"{offset + i:6}\t{line}" for i, line in enumerate(picked))
        return ToolResult(
            ok=True,
            content=f"{path}（共 {total} 行，展示 {len(picked)} 行）:\n{rendered}",
            artifacts={"path": str(path), "offset": offset, "totalLines": total},
        )

    return Tool(
        name="read",
        description=(
            "读取 UTF-8 文本文件（相对工作区路径或绝对路径），返回带行号内容，"
            "可指定 offset/limit 分页。写/编辑文件前必须先 read。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "文件路径（相对工作区或绝对）"},
                "offset": {"type": "integer", "description": "起始行（1 起），默认 1"},
                "limit": {
                    "type": "integer",
                    "description": f"最多行数，默认/上限 {MAX_READ_LINES}",
                },
            },
            "required": ["file_path"],
        },
        func=_read,
        permission=PERMISSION_READ,
    )


def _build_write(cwd: str, observed: dict) -> Tool:
    async def _write(file_path: str, content: str) -> ToolResult:
        path = _resolve(cwd, file_path)
        if not _in_workspace(cwd, path):
            return ToolResult(
                ok=False, error_code="OUT_OF_BOUNDS", content=f"目标不在工作区内，拒绝写入: {path}"
            )
        resolved = str(path.resolve())
        exists = path.exists()
        if exists:
            ver = _read_version(path)
            seen = observed.get(resolved)
            if seen is None:
                return ToolResult(
                    ok=False,
                    error_code="REQUIRE_READ",
                    content=f"需先 read 该文件再覆盖写入（防盲改）: {path}",
                )
            if ver != seen:
                return ToolResult(
                    ok=False,
                    error_code="FILE_CHANGED",
                    content=f"文件已被外部修改，请重新 read 后再写入: {path}",
                )
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write(path, content)
        except OSError as exc:
            return ToolResult(ok=False, error_code="WRITE_ERROR", content=str(exc))
        observed[resolved] = _read_version(path)
        return ToolResult(
            ok=True, content=f"已写入 {path}（{len(content)} 字符）", artifacts={"path": str(path)}
        )

    return Tool(
        name="write",
        description=(
            "创建或覆盖 UTF-8 文本文件（原子写）。覆盖已存在文件前必须先 read"
            "该文件（防止盲改）；新建文件无需。目标必须在工作区内。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "文件路径（相对工作区或绝对）"},
                "content": {"type": "string", "description": "完整文件内容"},
            },
            "required": ["file_path", "content"],
        },
        func=_write,
        permission=PERMISSION_WRITE,
    )


def _build_edit(cwd: str, observed: dict) -> Tool:
    async def _edit(
        file_path: str, old_string: str, new_string: str, replace_all: bool = False
    ) -> ToolResult:
        path = _resolve(cwd, file_path)
        if not _in_workspace(cwd, path):
            return ToolResult(
                ok=False, error_code="OUT_OF_BOUNDS", content=f"目标不在工作区内，拒绝编辑: {path}"
            )
        if not path.is_file():
            return ToolResult(ok=False, error_code="FILE_NOT_FOUND", content=f"文件不存在: {path}")
        resolved = str(path.resolve())
        ver = _read_version(path)
        seen = observed.get(resolved)
        if seen is None:
            return ToolResult(
                ok=False, error_code="REQUIRE_READ", content=f"需先 read 该文件再编辑: {path}"
            )
        if ver != seen:
            return ToolResult(
                ok=False,
                error_code="FILE_CHANGED",
                content=f"文件已被外部修改，请重新 read 再编辑: {path}",
            )
        if not old_string:
            return ToolResult(ok=False, error_code="EMPTY_OLD", content="old_string 不能为空")
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return ToolResult(ok=False, error_code="READ_ERROR", content=str(exc))
        count = text.count(old_string)
        if count == 0:
            return ToolResult(
                ok=False, error_code="NOT_FOUND", content=f"未找到匹配片段: {old_string[:60]!r}"
            )
        if count > 1 and not replace_all:
            return ToolResult(
                ok=False,
                error_code="NOT_UNIQUE",
                content=f"匹配 {count} 处，请提供更具体片段或 replace_all=true",
            )
        new_text = (
            text.replace(old_string, new_string)
            if replace_all
            else text.replace(old_string, new_string, 1)
        )
        try:
            _atomic_write(path, new_text)
        except OSError as exc:
            return ToolResult(ok=False, error_code="WRITE_ERROR", content=str(exc))
        observed[resolved] = _read_version(path)
        replaced = count if replace_all else 1
        return ToolResult(
            ok=True,
            content=f"已替换 {replaced} 处 -> {path}",
            artifacts={"path": str(path), "replaced": replaced},
        )

    return Tool(
        name="edit",
        description=(
            "在文件里做字面字符串替换（需先 read 且文件未被改动）。old_string"
            "必须唯一匹配，否则报错；replace_all=true 替换全部匹配。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "文件路径（相对工作区或绝对）"},
                "old_string": {"type": "string", "description": "要替换的原文片段（精确匹配）"},
                "new_string": {"type": "string", "description": "替换为"},
                "replace_all": {"type": "boolean", "description": "true=替换所有匹配，默认 false"},
            },
            "required": ["file_path", "old_string", "new_string"],
        },
        func=_edit,
        permission=PERMISSION_WRITE,
    )


def _build_glob(cwd: str) -> Tool:
    async def _glob(pattern: str, path: str | None = None) -> ToolResult:
        base = _resolve(cwd, path or ".")
        if not base.is_dir():
            return ToolResult(ok=False, error_code="DIR_NOT_FOUND", content=f"目录不存在: {base}")
        pat = pattern.replace("\\", "/")
        if "/" not in pat:
            pat = "**/" + pat  # 无 / 的 pattern 匹配任意深度 basename
        hits = [Path(m) for m in pyglob.glob(str(base / pat), recursive=True)]
        files = [p for p in hits if p.is_file()]
        rels = [str(p.relative_to(Path(cwd))).replace("\\", "/") for p in files[:MAX_GLOB]]
        truncated = len(files) > MAX_GLOB
        content = "\n".join(rels) if rels else "(无匹配)"
        if truncated:
            content += f"\n...(共 {len(files)} 个，仅展示 {MAX_GLOB})"
        return ToolResult(
            ok=True,
            content=content,
            artifacts={"matches": rels, "truncated": truncated},
        )

    return Tool(
        name="glob",
        description=(
            "按通配符在工作区里发现文件（如 **/*.py、*.py、services/**/tasks.py）。"
            "返回相对工作区路径，最多 100 条。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "glob 模式，** 递归"},
                "path": {"type": "string", "description": "可选搜索根目录（相对工作区）"},
            },
            "required": ["pattern"],
        },
        func=_glob,
        permission=PERMISSION_READ,
    )


def _build_grep(cwd: str) -> Tool:
    async def _grep(
        pattern: str, path: str | None = None, include: str | None = None
    ) -> ToolResult:
        base = _resolve(cwd, path or ".")
        if not base.is_dir():
            return ToolResult(ok=False, error_code="DIR_NOT_FOUND", content=f"目录不存在: {base}")
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            return ToolResult(ok=False, error_code="BAD_PATTERN", content=f"正则不合法: {exc}")
        matches: list[str] = []
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            if any(part in _SKIP_DIRS for part in p.parts):
                continue
            if p.suffix.lower() in _SKIP_SUFFIXES:
                continue
            if include and not p.match(include):
                continue
            try:
                with open(p, "rb") as f:
                    for i, raw in enumerate(f, 1):
                        if len(matches) >= MAX_GREP_MATCHES:
                            break
                        try:
                            line = raw.decode("utf-8")
                        except UnicodeDecodeError:
                            break
                        if rx.search(line):
                            text = line.rstrip()
                            if len(text.encode("utf-8")) > MAX_GREP_LINE_BYTES:
                                text = text[:500] + "…"
                            matches.append(
                                f"{str(p.relative_to(Path(cwd))).replace(chr(92), '/')}:{i}: {text}"
                            )
                    if len(matches) >= MAX_GREP_MATCHES:
                        break
            except OSError:
                continue
        content = "\n".join(matches) if matches else "(无匹配)"
        return ToolResult(ok=True, content=content, artifacts={"matches": len(matches)})

    return Tool(
        name="grep",
        description=(
            "在工作区文件内容里搜索正则表达式，返回 文件:行号: 匹配行"
            "（最多 250 条）。跳过 .git/node_modules/二进制等。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "正则表达式"},
                "path": {"type": "string", "description": "可选搜索根目录（相对工作区）"},
                "include": {"type": "string", "description": "可选文件名 glob 过滤"},
            },
            "required": ["pattern"],
        },
        func=_grep,
        permission=PERMISSION_READ,
    )


# ---------------------------------------------------------------------------
# bash 工具
# ---------------------------------------------------------------------------


def _build_bash(cwd: str) -> Tool:
    bash = _find_bash()

    async def _bash(
        command: str, workdir: str | None = None, timeout: float = BASH_DEFAULT_TIMEOUT
    ) -> ToolResult:
        cdir = _resolve(cwd, workdir) if workdir else Path(cwd)
        if not cdir.is_dir():
            return ToolResult(
                ok=False, error_code="DIR_NOT_FOUND", content=f"工作目录不存在: {cdir}"
            )
        t = max(1.0, min(float(timeout), BASH_MAX_TIMEOUT))
        env = {**os.environ, "NO_COLOR": "1", "TERM": "dumb", "PAGER": "cat", "GIT_PAGER": "cat"}
        proc = await asyncio.create_subprocess_exec(
            bash,
            "-c",
            command,
            cwd=str(cdir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=t)
        except TimeoutError:
            proc.kill()
            with contextlib.suppress(Exception):  # 清理尽力而为
                await asyncio.wait_for(proc.communicate(), timeout=2)
            return ToolResult(
                ok=False,
                error_code="BASH_TIMEOUT",
                content=f"命令超时({t}s)已终止: {command[:120]}",
            )
        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        parts = []
        if stdout:
            parts.append("stdout:\n" + _cap(stdout, BASH_MAX_OUTPUT))
        if stderr:
            parts.append("stderr:\n" + _cap(stderr, BASH_MAX_OUTPUT))
        if not parts:
            parts.append("(无输出，退出码 0)")
        ok = proc.returncode == 0
        return ToolResult(
            ok=ok,
            content=f"[exit {proc.returncode}]（{cdir}）\n" + "\n\n".join(parts),
            artifacts={"exit_code": proc.returncode, "cwd": str(cdir), "timeout_s": t},
        )

    return Tool(
        name="bash",
        description=(
            "在指定工作目录执行 shell 命令（Git Bash，每次全新进程，无持久状态"
            "——需要换目录用 workdir 参数，不要用 cd）。"
            f"默认超时 {BASH_DEFAULT_TIMEOUT}s（上限 {BASH_MAX_TIMEOUT}s），"
            f"输出超 {BASH_MAX_OUTPUT} 字节截断。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的 shell 命令"},
                "workdir": {"type": "string", "description": "可选工作目录（相对工作区或绝对）"},
                "timeout": {
                    "type": "number",
                    "description": f"超时秒数（默认 {BASH_DEFAULT_TIMEOUT}）",
                },
            },
            "required": ["command"],
        },
        func=_bash,
        permission=PERMISSION_DESTRUCTIVE,  # F2.4：执行任意命令=破坏性，默认需审批（dev 自动放行）
    )


def build_workspace_tools(cwd: str) -> list[Tool]:
    """构建绑定工作区 cwd 的工具集（read/write/edit/glob/grep + bash）。

    每次调用创建独立 observed 状态（随任务生命周期，跨任务隔离）。
    """
    observed: dict[str, tuple[int, int]] = {}
    return [
        _build_read(cwd, observed),
        _build_write(cwd, observed),
        _build_edit(cwd, observed),
        _build_glob(cwd),
        _build_grep(cwd),
        _build_bash(cwd),
    ]
