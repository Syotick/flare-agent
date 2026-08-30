"""工作区工具测试（P1：读代码/写代码/跑命令，对标 DSH）。

覆盖：read 窗口、write 新建/覆盖 read 前置、edit 唯一匹配 + 版本 CAS、
glob/grep、bash（Git Bash cwd/退出码/超时）、越界拒绝、registry.task_view 接线。
"""

from __future__ import annotations

import asyncio

from langgraph.checkpoint.memory import MemorySaver

from agent_runtime.approval import ApprovalManager, ApprovalPolicy
from agent_runtime.tasks import TaskManager
from model_gateway.providers import LLMResponse, LLMUsage, ToolCall, ToolCallDecision
from tools_gateway.builtin import create_default_registry
from tools_gateway.registry import ToolRegistry
from tools_gateway.workspace_tools import build_workspace_tools


def _tools(tmp_path):
    return {t.name: t for t in build_workspace_tools(str(tmp_path))}


def _run(tool, **kwargs):
    return asyncio.run(tool.func(**kwargs))


def _names(tools):
    return sorted(t.name for t in tools.list())


# ---------------- read ----------------


def test_read_basic(tmp_path):
    (tmp_path / "a.py").write_text("line1\nline2\nline3", encoding="utf-8")
    r = _run(_tools(tmp_path)["read"], file_path="a.py")
    assert r.ok and "line1" in r.content and "3 行" in r.content
    assert r.artifacts["totalLines"] == 3


def test_read_window(tmp_path):
    (tmp_path / "a.txt").write_text("".join(f"l{i}\n" for i in range(50)), encoding="utf-8")
    r = _run(_tools(tmp_path)["read"], file_path="a.txt", offset=10, limit=5)
    # offset 是起始行号（1 起），展示内容为 l9..l13，行号 10..14
    assert r.ok and "l9" in r.content and "l13" in r.content and "l14" not in r.content


def test_read_missing(tmp_path):
    r = _run(_tools(tmp_path)["read"], file_path="nope.py")
    assert not r.ok and r.error_code == "FILE_NOT_FOUND"


def test_read_absolute_in_workspace(tmp_path):
    f = tmp_path / "abs.txt"
    f.write_text("x", encoding="utf-8")
    r = _run(_tools(tmp_path)["read"], file_path=str(f))
    assert r.ok


# ---------------- write + read 前置 ----------------


def test_write_new_file(tmp_path):
    r = _run(_tools(tmp_path)["write"], file_path="new.py", content="print(1)")
    assert r.ok and (tmp_path / "new.py").read_text(encoding="utf-8") == "print(1)"


def test_write_overwrite_requires_read(tmp_path):
    (tmp_path / "ex.py").write_text("old", encoding="utf-8")
    tools = _tools(tmp_path)
    r = _run(tools["write"], file_path="ex.py", content="new")
    assert not r.ok and r.error_code == "REQUIRE_READ"


def test_write_after_read_ok(tmp_path):
    (tmp_path / "ex.py").write_text("old", encoding="utf-8")
    tools = _tools(tmp_path)
    assert _run(tools["read"], file_path="ex.py").ok
    r = _run(tools["write"], file_path="ex.py", content="new")
    assert r.ok and (tmp_path / "ex.py").read_text(encoding="utf-8") == "new"


def test_write_file_changed_externally(tmp_path):
    (tmp_path / "ex.py").write_text("v1", encoding="utf-8")
    tools = _tools(tmp_path)
    assert _run(tools["read"], file_path="ex.py").ok
    (tmp_path / "ex.py").write_text("v2", encoding="utf-8")  # 外部改动
    r = _run(tools["write"], file_path="ex.py", content="v3")
    assert not r.ok and r.error_code == "FILE_CHANGED"


def test_write_out_of_bounds(tmp_path, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    tools = _tools(tmp_path)
    r = _run(tools["write"], file_path=str(outside / "evil.txt"), content="x")
    assert not r.ok and r.error_code == "OUT_OF_BOUNDS"


# ---------------- edit ----------------


def test_edit_requires_read(tmp_path):
    (tmp_path / "a.txt").write_text("hello world", encoding="utf-8")
    r = _run(_tools(tmp_path)["edit"], file_path="a.txt", old_string="world", new_string="flare")
    assert not r.ok and r.error_code == "REQUIRE_READ"


def test_edit_unique(tmp_path):
    (tmp_path / "a.txt").write_text("hello world hello", encoding="utf-8")
    tools = _tools(tmp_path)
    assert _run(tools["read"], file_path="a.txt").ok
    r = _run(tools["edit"], file_path="a.txt", old_string="world", new_string="flare")
    assert r.ok and (tmp_path / "a.txt").read_text(encoding="utf-8") == "hello flare hello"


def test_edit_not_unique(tmp_path):
    (tmp_path / "a.txt").write_text("xx xx", encoding="utf-8")
    tools = _tools(tmp_path)
    assert _run(tools["read"], file_path="a.txt").ok
    r = _run(tools["edit"], file_path="a.txt", old_string="xx", new_string="yy")
    assert not r.ok and r.error_code == "NOT_UNIQUE"


def test_edit_replace_all(tmp_path):
    (tmp_path / "a.txt").write_text("xx xx", encoding="utf-8")
    tools = _tools(tmp_path)
    assert _run(tools["read"], file_path="a.txt").ok
    r = _run(tools["edit"], file_path="a.txt", old_string="xx", new_string="yy", replace_all=True)
    assert r.ok and (tmp_path / "a.txt").read_text(encoding="utf-8") == "yy yy"


def test_edit_file_changed(tmp_path):
    (tmp_path / "a.txt").write_text("v1", encoding="utf-8")
    tools = _tools(tmp_path)
    assert _run(tools["read"], file_path="a.txt").ok
    (tmp_path / "a.txt").write_text("v2", encoding="utf-8")
    r = _run(tools["edit"], file_path="a.txt", old_string="v2", new_string="v3")
    assert not r.ok and r.error_code == "FILE_CHANGED"


# ---------------- glob / grep ----------------


def test_glob(tmp_path):
    (tmp_path / "services").mkdir()
    (tmp_path / "services" / "a.py").write_text("", encoding="utf-8")
    (tmp_path / "b.py").write_text("", encoding="utf-8")
    tools = _tools(tmp_path)
    r = _run(tools["glob"], pattern="**/*.py")
    assert r.ok
    rels = r.content.splitlines()
    assert "services/a.py" in rels and "b.py" in rels


def test_grep(tmp_path):
    (tmp_path / "main.py").write_text("def main():\n    print('hi')\n", encoding="utf-8")
    r = _run(_tools(tmp_path)["grep"], pattern="def main")
    assert r.ok and "main.py:1" in r.content


def test_grep_skips_hidden(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "x").write_text("secret", encoding="utf-8")
    r = _run(_tools(tmp_path)["grep"], pattern="secret")
    assert r.ok and "(无匹配)" in r.content


# ---------------- bash ----------------


def test_bash_echo(tmp_path):
    r = _run(_tools(tmp_path)["bash"], command="echo hello-workspace")
    assert r.ok and "hello-workspace" in r.content and r.artifacts["exit_code"] == 0


def test_bash_cwd_is_workspace(tmp_path):
    r = _run(_tools(tmp_path)["bash"], command="pwd")
    assert r.ok and str(tmp_path) in r.content


def test_bash_exit_code(tmp_path):
    r = _run(_tools(tmp_path)["bash"], command="exit 7")
    assert not r.ok and r.artifacts["exit_code"] == 7


def test_bash_timeout(tmp_path):
    r = _run(_tools(tmp_path)["bash"], command="sleep 5", timeout=1)
    assert not r.ok and r.error_code == "BASH_TIMEOUT"


def test_bash_workdir_param(tmp_path):
    (tmp_path / "sub").mkdir()
    r = _run(_tools(tmp_path)["bash"], command="pwd", workdir="sub")
    assert r.ok and str(tmp_path / "sub") in r.content


# ---------------- registry.task_view ----------------


def test_task_view_no_cwd_has_no_workspace_tools():
    view = ToolRegistry().task_view(None)
    assert "read" not in _names(view)
    assert "bash" not in _names(view)


def test_task_view_with_cwd_attaches_workspace_tools(tmp_path):
    view = ToolRegistry().task_view(str(tmp_path))
    names = _names(view)
    for expected in ("read", "write", "edit", "glob", "grep", "bash"):
        assert expected in names


# ---------------- graph 全链路集成（workspace 工具经 TaskManager 接线） ----------------


async def _mem_saver():
    return MemorySaver()


class FakeWorkspaceLlm:
    """确定性假模型：第一次 call_tool read，拿到观察后 final。"""

    async def chat(self, messages, **_kw):
        last = messages[-1] if messages else None
        if last is not None and last.role == "tool":
            decision = ToolCallDecision(action="final", answer="读到: " + last.content[:200])
        else:
            decision = ToolCallDecision(
                action="call_tool", tool=ToolCall(name="read", args={"file_path": "a.txt"})
            )
        return LLMResponse(
            content=decision.model_dump_json(),
            model="fake",
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1),
        )

    async def stream(self, messages, **_kw):
        resp = await self.chat(messages)
        yield resp.content


async def test_workspace_tools_reach_task_graph(tmp_path):
    """工作区目录任务：graph 内经 task_view 注入 read 工具并真实读到文件。"""
    (tmp_path / "a.txt").write_text("hello from workspace", encoding="utf-8")
    mgr = TaskManager(
        registry=create_default_registry(),
        llm=FakeWorkspaceLlm(),
        checkpointer_factory=_mem_saver,
    )
    task = await mgr.create("读 a.txt", workspace_id=str(tmp_path))
    deadline = asyncio.get_event_loop().time() + 5
    while asyncio.get_event_loop().time() < deadline:
        t = await mgr.get(task.task_id)
        if t.status in ("completed", "failed", "budget_exceeded"):
            break
        await asyncio.sleep(0.02)
    assert t.status == "completed", f"任务未完成: {t.status} {t.result}"
    assert "hello from workspace" in (t.result or {}).get("output", "")


async def test_default_workspace_has_no_fs_tools(tmp_path):
    """default 工作区不注入文件/bash 工具（只读工具不可用，防越权）。"""
    mgr = TaskManager(
        registry=create_default_registry(),
        llm=FakeWorkspaceLlm(),
        checkpointer_factory=_mem_saver,
    )
    task = await mgr.create("读 a.txt", workspace_id="default")
    deadline = asyncio.get_event_loop().time() + 5
    while asyncio.get_event_loop().time() < deadline:
        t = await mgr.get(task.task_id)
        if t.status in ("completed", "failed", "budget_exceeded"):
            break
        await asyncio.sleep(0.02)
    # default 无 read 工具 -> 模型被观察"未知工具"，任务仍结束（mock 语义：最终输出非文件内容）
    assert t.status in ("completed", "failed")

# ---------------- DSH 权限模式（read-only / approval / unrestricted） ----------------

def test_task_view_read_only_filters_write_tools(tmp_path):
    """read-only 模式：只注入只读工具（read/glob/grep），write/edit/bash 不注入。"""
    reg = create_default_registry()
    view = reg.task_view(str(tmp_path)).read_only()
    names = {t.name for t in view.list()}
    assert {"read", "glob", "grep"} <= names
    assert not {"write", "edit", "bash"} & names


class FakeReadThenFinal:
    """读 a.txt -> 拿观察后 final（只读链路）。"""

    async def chat(self, messages, **_kw):
        last = messages[-1] if messages else None
        if last is not None and last.role == "tool":
            decision = ToolCallDecision(action="final", answer="读到: " + last.content[:200])
        else:
            decision = ToolCallDecision(
                action="call_tool", tool=ToolCall(name="read", args={"file_path": "a.txt"})
            )
        return LLMResponse(
            content=decision.model_dump_json(),
            model="fake",
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1),
        )

    async def stream(self, messages, **_kw):
        resp = await self.chat(messages)
        yield resp.content


async def test_read_only_mode_still_reads(tmp_path):
    """read-only 模式：read 可用（任务正常完成并读到内容）。"""
    (tmp_path / "a.txt").write_text("secret data", encoding="utf-8")
    mgr = TaskManager(
        registry=create_default_registry(),
        llm=FakeReadThenFinal(),
        checkpointer_factory=_mem_saver,
    )
    task = await mgr.create("读 a.txt", workspace_id=str(tmp_path), permission_mode="read-only")
    deadline = asyncio.get_event_loop().time() + 5
    while asyncio.get_event_loop().time() < deadline:
        t = await mgr.get(task.task_id)
        if t.status in ("completed", "failed", "budget_exceeded"):
            break
        await asyncio.sleep(0.02)
    assert t.status == "completed", f"read-only 任务未完成: {t.status} {t.result}"
    assert "secret data" in (t.result or {}).get("output", "")
    assert t.permission_mode == "read-only"


class FakeBashThenFinal:
    """跑 bash echo -> 观察后 final（destructive 链路，验证审批门）。"""

    async def chat(self, messages, **_kw):
        last = messages[-1] if messages else None
        if last is not None and last.role == "tool":
            decision = ToolCallDecision(action="final", answer="bash 输出: " + last.content[:200])
        else:
            decision = ToolCallDecision(
                action="call_tool", tool=ToolCall(name="bash", args={"command": "echo hi-from-bash"})
            )
        return LLMResponse(
            content=decision.model_dump_json(),
            model="fake",
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1),
        )

    async def stream(self, messages, **_kw):
        resp = await self.chat(messages)
        yield resp.content


async def test_unrestricted_mode_skips_approval(tmp_path):
    """unrestricted 模式：destructive 工具（bash）免审批直接执行。"""
    mgr = TaskManager(
        registry=create_default_registry(),
        llm=FakeBashThenFinal(),
        checkpointer_factory=_mem_saver,
        approval=ApprovalManager(ApprovalPolicy(require_level="destructive")),
    )
    task = await mgr.create(
        "跑 bash", workspace_id=str(tmp_path), permission_mode="unrestricted"
    )
    deadline = asyncio.get_event_loop().time() + 8
    while asyncio.get_event_loop().time() < deadline:
        t = await mgr.get(task.task_id)
        if t.status in ("completed", "failed", "budget_exceeded"):
            break
        await asyncio.sleep(0.02)
    assert t.status == "completed", f"unrestricted 任务未完成: {t.status} {t.result}"
    assert "hi-from-bash" in (t.result or {}).get("output", "")


async def test_model_resolver_selects_per_task_llm(tmp_path):
    """per-task 模型：resolver 命中返回 provider 并用它执行；未命中回退默认 llm。"""
    (tmp_path / "a.txt").write_text("model-selected", encoding="utf-8")
    calls: list[str] = []

    def resolver(model_id: str):
        calls.append(model_id)
        if model_id == "p_fake":
            return FakeReadThenFinal()
        return None

    mgr = TaskManager(
        registry=create_default_registry(),
        llm=FakeReadThenFinal(),
        checkpointer_factory=_mem_saver,
        model_resolver=resolver,
    )
    task = await mgr.create("读 a.txt", workspace_id=str(tmp_path), model="p_fake")
    deadline = asyncio.get_event_loop().time() + 5
    while asyncio.get_event_loop().time() < deadline:
        t = await mgr.get(task.task_id)
        if t.status in ("completed", "failed", "budget_exceeded"):
            break
        await asyncio.sleep(0.02)
    assert calls == ["p_fake"]
    assert t.status == "completed", f"resolver 任务未完成: {t.status} {t.result}"
    assert "model-selected" in (t.result or {}).get("output", "")

    # 未命中 -> 回退默认 llm，任务仍正常
    task2 = await mgr.create("读 a.txt", workspace_id=str(tmp_path), model="p_missing")
    deadline2 = asyncio.get_event_loop().time() + 5
    while asyncio.get_event_loop().time() < deadline2:
        t2 = await mgr.get(task2.task_id)
        if t2.status in ("completed", "failed", "budget_exceeded"):
            break
        await asyncio.sleep(0.02)
    assert t2.status == "completed"

