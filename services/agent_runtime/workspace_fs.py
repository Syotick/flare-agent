"""工作区文件系统原语（对标 DSH host.listDirectory / createDirectory）。

工作区 = 服务器（Host）上的真实目录路径。浏览器 UI 通过本 API 浏览/创建目录，
选中路径作为 workspace_id —— 复刻 DSH 的 browse 目录选择器后端。

安全边界：
- 只列目录与符号链接（工作区选择只看目录，不暴露文件内容）；
- hidden 项（以 . 开头）也返回，由前端过滤显示（对齐 DSH）；
- 每层上限 max_entries（默认 1000），防止爆炸；
- 不存在/无权限/非法名/冲突 -> 具体 FlareError 子类（app 统一错误契约）。
"""

from __future__ import annotations

import os
import string
from pathlib import Path

from flare_common.errors import FlareError


class WorkspaceFsError(FlareError):
    code = "WORKSPACE_FS_ERROR"
    status_code = 400


class DirNotFoundError(WorkspaceFsError):
    code = "DIR_NOT_FOUND"
    status_code = 404


class NotADirError(WorkspaceFsError):
    code = "NOT_A_DIR"
    status_code = 422


class InvalidNameError(WorkspaceFsError):
    code = "INVALID_NAME"
    status_code = 422


class DirAlreadyExistsError(WorkspaceFsError):
    code = "ALREADY_EXISTS"
    status_code = 409


def _hidden(name: str) -> bool:
    return name.startswith(".")


def _list_root() -> list[dict]:
    """跨平台根级：Windows 枚举存在的盘符；POSIX 返回 /。"""
    if os.name == "nt":
        return [
            {"name": f"{letter}:\\", "is_dir": True, "hidden": False}
            for letter in string.ascii_uppercase
            if os.path.exists(f"{letter}:\\")
        ]
    return [{"name": "/", "is_dir": True, "hidden": False}]


def list_directory(path: str | None = None, max_entries: int = 1000) -> dict:
    """列出目录下的子目录（对标 host.listDirectory）。

    - path 为空 -> 根级（Windows 盘符 / POSIX /）；
    - 返回 {path, parent, entries:[{name,is_dir,hidden}], truncated}；
    - parent 用于前端"向上"导航（根级 parent=None）。
    """
    if not path:
        return {"path": "", "parent": None, "entries": _list_root(), "truncated": False}
    p = Path(path)
    if not p.exists():
        raise DirNotFoundError(f"目录不存在: {path}")
    if not p.is_dir():
        raise NotADirError(f"不是目录: {path}")
    try:
        rows = []
        with os.scandir(p) as it:
            for ent in it:
                try:
                    is_dir = ent.is_dir(follow_symlinks=True)
                    is_link = ent.is_symlink()
                except OSError:
                    continue  # 单个条目 stat 失败（权限/断链）跳过，不阻塞整层
                if not (is_dir or is_link):
                    continue  # 只列目录与符号链接
                rows.append({"name": ent.name, "is_dir": is_dir, "hidden": _hidden(ent.name)})
    except OSError as exc:
        raise WorkspaceFsError(f"无法读取目录 {path}: {exc}") from exc
    rows.sort(key=lambda r: (r["hidden"], r["name"].lower()))
    truncated = len(rows) > max_entries
    resolved = str(p.resolve())
    parent = str(p.parent) if p.parent != p else None
    return {
        "path": resolved,
        "parent": parent,
        "entries": rows[:max_entries],
        "truncated": truncated,
    }


def create_directory(path: str, name: str) -> str:
    """在 path 下创建子目录 name；冲突 409 / 非法名 422 / 失败 5xx。"""
    name = (name or "").strip()
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        raise InvalidNameError("非法的目录名")
    parent = Path(path)
    if not parent.exists() or not parent.is_dir():
        raise DirNotFoundError(f"目录不存在: {path}")
    target = parent / name
    if target.exists():
        raise DirAlreadyExistsError(f"已存在: {target}")
    try:
        target.mkdir()
    except OSError as exc:
        raise WorkspaceFsError(f"创建目录失败: {exc}") from exc
    return str(target)
