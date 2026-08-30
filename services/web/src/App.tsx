import { useEffect, useRef, useState } from "react";
import { createTask, deleteTask, getTask, listApprovals, listTasks, listWorkspaces } from "./api";
import ApiView from "./components/ApiView";
import ApprovalsView from "./components/ApprovalsView";
import CapabilitiesView from "./components/CapabilitiesView";
import ModelSettingsView from "./components/ModelSettingsView";
import ChatView from "./components/ChatView";
import Composer from "./components/Composer";
import KnowledgeBaseView from "./components/KnowledgeBaseView";
import MemoryView from "./components/MemoryView";
import OpsView from "./components/OpsView";
import Sidebar from "./components/Sidebar";
import type { Item } from "./types";

export type ViewId = "chat" | "kb" | "memory" | "ops" | "capabilities" | "api" | "approvals" | "model";

// 由 vite define 注入的构建时间戳（前端版本标识）
declare const __BUILD_TIME__: string;
const BUILD_TAG = typeof __BUILD_TIME__ !== "undefined" ? __BUILD_TIME__.slice(0, 19).replace("T", " ") : "";

let nextId = 1;
// 实时消息时间戳（秒）：新会话消息显示，历史回放（无 ts）不显示，保持干净
const nowTs = () => Math.floor(Date.now() / 1000);

interface ResultPayload {
  result: { status: string; output: string; step_count: number; message_count: number } | null;
  status: string;
  error?: string | null;
}

function parseSSE<T>(raw: string): T | null {
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function streamUrl(taskId: string): string {
  return "/v1/tasks/" + taskId + "/stream";
}

const statusText = (s: string) =>
  s === "completed" ? "已完成"
  : s === "failed" ? "失败"
  : s === "budget_exceeded" ? "预算超限"
  : "已结束";

// 内部参数（对用户不可见，产品层不给用户配置工程细节）
const MAX_STEPS = 8; // Agent 单次任务最大思考→行动轮次

export default function App() {
  const [view, setView] = useState<ViewId>("chat");
  const [input, setInput] = useState("");
  // thread_id 由系统管理：新建会话=空(自动生成)；切换会话=沿用该会话线程（续聊上下文）
  const [threadId, setThreadId] = useState("");
  const [running, setRunning] = useState(false);
  const [items, setItems] = useState<Item[]>([]);
  const [tasks, setTasks] = useState<import("./api").TaskDetail[]>([]);
  // DSH 对齐：工作区（先选工作区再新建对话；无默认工作区，对话从属工作区）
  const [currentWorkspace, setCurrentWorkspace] = useState<string | null>(null);
  const [workspaces, setWorkspaces] = useState<import("./api").Workspace[]>([]);
  // 每个工作区的对话视图状态缓存：切换工作区保留（不会切走就刷没），切回直接恢复
  const workspaceCache = useRef<Record<string, { items: Item[]; activeTaskId: string | null; threadId: string; input: string }>>({});
  const [pendingApprovals, setPendingApprovals] = useState(0);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const lastToolId = useRef<number | null>(null);
  const lastAssistantId = useRef<number | null>(null);

  const refreshHistory = () => {
    if (!currentWorkspace) {
      setTasks([]); // 未选工作区：不展示任何会话
      return;
    }
    listTasks(currentWorkspace).then(setTasks).catch(() => undefined);
  };

  const refreshWorkspaces = () => {
    listWorkspaces().then(setWorkspaces).catch(() => undefined);
  };

  useEffect(() => {
    refreshHistory();
    refreshWorkspaces();
  }, []);

  // F1.3 审批中心：轮询待审批数，驱动侧栏徽标（有审批时审批中心也会自刷新）
  useEffect(() => {
    const load = () =>
      listApprovals(true)
        .then((l) => setPendingApprovals(l.length))
        .catch(() => undefined);
    load();
    const timer = window.setInterval(load, 8000);
    return () => window.clearInterval(timer);
  }, []);

  // 刷新恢复：回放该会话轨迹，并沿用其线程（续聊上下文连续）
  useEffect(() => {
    const hash = window.location.hash.match(/task=([a-f0-9]+)/);
    if (hash) {
      const tid = hash[1];
      setItems([]);
      setActiveTaskId(tid);
      setRunning(true);
      lastAssistantId.current = null;
      lastToolId.current = null;
      getTask(tid)
        .then((d) => {
          setThreadId(d.thread_id);
          if (d.status !== "pending" && d.status !== "running") setRunning(false);
        })
        .catch(() => setRunning(false));
    }
  }, []);

  // SSE 生命周期
  useEffect(() => {
    if (!activeTaskId) return;
    let finished = false;
    let closed = false;
    const es = new EventSource(streamUrl(activeTaskId));
    const stall = window.setTimeout(() => {
      es.close();
      setRunning(false);
    }, 30000);

    es.addEventListener("step", (ev) => {
      window.clearTimeout(stall);
      const data = parseSSE<{ type: string; node?: string[]; data?: Record<string, any>; content?: string }>((ev as MessageEvent).data);
      if (!data) return;
      // L6：token 级流式——模型每吐一段，实时追加到当前助手气泡（打字机效果）
      if (data.type === "token") {
        const tok = data.content;
        if (typeof tok !== "string") return;
        const lid = lastAssistantId.current;
        if (lid !== null) {
          setItems((prev) =>
            prev.map((it) =>
              it.kind === "assistant" && it.id === lid
                ? { ...it, msg: { ...it.msg, text: it.msg.text + tok } }
                : it
            )
          );
        } else {
          const id = nextId++;
          lastAssistantId.current = id;
          setItems((prev) => [...prev, { id, kind: "assistant", msg: { text: tok, done: false }, ts: nowTs() }]);
        }
        return;
      }
      // F1.3 审批：新请求 -> 插入审批卡片；决策回灌 -> 更新卡片状态
      if (data.type === "approval" && data.data?.approval) {
        const appr = data.data.approval;
        setItems((prev) => [...prev, { id: nextId++, kind: "approval", approval: appr }]);
        return;
      }
      if (data.type === "approval_decision" && data.data?.approval) {
        const appr = data.data.approval;
        setItems((prev) =>
          prev.map((it) =>
            it.kind === "approval" && it.approval.approval_id === appr.approval_id
              ? { ...it, approval: { ...it.approval, ...appr } }
              : it
          )
        );
        return;
      }
      const nodes = Array.isArray(data.node) ? data.node : [];
      if (nodes.includes("actor") && data.data?.actor) {
        const actor = data.data.actor;
        if (actor.action === "call_tool" && actor.pending_tool) {
          const id = nextId++;
          lastToolId.current = id;
          setItems((prev) => [
            ...prev,
            { id, kind: "tool", name: actor.pending_tool.name, args: actor.pending_tool.args || {}, status: "running" },
          ]);
        }
        if (actor.action === "final" && actor.output) {
          const lid = lastAssistantId.current;
          if (lid !== null) {
            // token 已在流式累积 → 用最终 output 对齐文本（防缺段/截断）；
            // done 由 result 延迟设置，保证打字机动画可见
            setItems((prev) =>
              prev.map((it) =>
                it.kind === "assistant" && it.id === lid
                  ? { ...it, msg: { text: actor.output, done: false } }
                  : it
              )
            );
          } else {
            const id = nextId++;
            lastAssistantId.current = id;
            setItems((prev) => [...prev, { id, kind: "assistant", msg: { text: actor.output, done: false }, ts: nowTs() }]);
          }
        }
      }
      if (nodes.includes("tool_executor") && data.data?.tool_executor) {
        const te = data.data.tool_executor;
        const r = te.last_tool_result;
        const id = lastToolId.current;
        if (id != null && r) {
          setItems((prev) =>
            prev.map((it) =>
              it.id === id && it.kind === "tool"
                ? { ...it, status: "done" as const, result: { ok: r.ok, content: r.content, error_code: r.error_code, artifacts: r.artifacts || {} } }
                : it
            )
          );
        }
      }
    });

    es.addEventListener("result", (ev) => {
      finished = true;
      window.clearTimeout(stall);
      const data = parseSSE<ResultPayload>((ev as MessageEvent).data);
      const aid = lastAssistantId.current;
      if (aid != null) {
        // L6：不立即 done——给打字机时间把剩余文本逐字打完（token 快时 result 紧跟会秒全显）
        const outLen = (data?.result?.output ?? "").length;
        const delay = Math.min(5000, 500 + outLen * 20); // ≈20ms/字符 + 缓冲，封顶 5s
        window.setTimeout(() => {
          setItems((prev) =>
            prev.map((it) => (it.id === aid && it.kind === "assistant" ? { ...it, msg: { ...it.msg, done: true } } : it))
          );
        }, delay);
      } else if (data?.result?.output) {
        // 兜底：token/final 均未渲染时，用 result 完整输出显示回复
        const id = nextId++;
        lastAssistantId.current = id;
        setItems((prev) => [...prev, { id, kind: "assistant", msg: { text: data.result!.output, done: true }, ts: nowTs() }]);
      }
      if (data) {
        setItems((prev) => [
          ...prev,
          {
            id: nextId++,
            kind: "status",
            text: statusText(data.status),
            tone: data.status === "completed" ? "info" : data.status === "failed" ? "error" : "warn",
          },
        ]);
      }
      es.close();
      setRunning(false);
      refreshHistory();
    });

    es.onerror = () => {
      window.clearTimeout(stall);
      es.close();
      setRunning(false);
      if (!closed && !finished) {
        setItems((prev) => [...prev, { id: nextId++, kind: "status", text: "连接中断，已停止", tone: "error" }]);
      }
    };

    return () => {
      closed = true;
      window.clearTimeout(stall);
      es.close();
    };
  }, [activeTaskId]);

  const rememberTask = (taskId: string) => {
    const url = new URL(window.location.href);
    url.hash = "#task=" + taskId;
    window.history.replaceState(null, "", url.toString());
    try {
      localStorage.setItem("flare.lastTaskId", taskId);
    } catch {
      // ignore
    }
  };

  const send = async (text?: string) => {
    const content = (text ?? input).trim();
    if (!content || running) return;
    if (!currentWorkspace) {
      setItems((prev) => [
        ...prev,
        { id: nextId++, kind: "status", text: "请先选择或创建工作区，再开始对话", tone: "warn" },
      ]);
      return;
    }
    setRunning(true);
    setInput("");
    // 新任务 = 新回复气泡：重置流式定位，避免 token 追加到上一轮的助手气泡
    lastAssistantId.current = null;
    lastToolId.current = null;
    setItems((prev) => [...prev, { id: nextId++, kind: "user", text: content, ts: nowTs() }]);
    try {
      const created = await createTask(content, MAX_STEPS, threadId || undefined, currentWorkspace);
      // 同步服务端生成的线程：同会话后续消息自动续聊（上下文连续，无需用户关心 thread_id）
      setThreadId(created.thread_id);
      rememberTask(created.task_id);
      setActiveTaskId(created.task_id);
      setItems((prev) => [
        ...prev,
        { id: nextId++, kind: "status", text: "已提交，执行中…", tone: "info" },
      ]);
    } catch (err) {
      setRunning(false);
      setItems((prev) => [
        ...prev,
        { id: nextId++, kind: "status", text: err instanceof Error ? err.message : String(err), tone: "error" },
      ]);
    }
  };

  const cancel = () => {
    setActiveTaskId(null);
    setRunning(false);
    setItems((prev) => [...prev, { id: nextId++, kind: "status", text: "已停止", tone: "warn" }]);
  };

  const pickTask = (taskId: string) => {
    // 切换会话：先放该会话的用户消息（SSE 只回放 assistant 侧事件，user 消息需要从
    // 任务数据恢复，否则历史会话会丢失用户输入），随后 SSE 重放助手回复与工具轨迹
    setItems([]);
    setRunning(true);
    setActiveTaskId(taskId);
    rememberTask(taskId);
    lastAssistantId.current = null;
    lastToolId.current = null;
    // 沿用该会话的线程：后续发言在同一线程续聊，上下文连续
    const found = tasks.find((t) => t.task_id === taskId);
    setThreadId(found ? found.thread_id : "");
    if (found?.task_input) {
      setItems((prev) => [...prev, { id: nextId++, kind: "user", text: found.task_input }]);
    }
    getTask(taskId)
      .then((d) => {
        // tasks 列表可能没有该任务（如刷新恢复、多实例），用详情补 user 消息
        if (!found && d.task_input) {
          setItems((prev) => [...prev, { id: nextId++, kind: "user", text: d.task_input }]);
        }
        if (d.status !== "pending" && d.status !== "running") setRunning(false);
      })
      .catch(() => setRunning(false));
  };

  const handleDelete = async (taskId: string) => {
    try {
      await deleteTask(taskId);
      if (activeTaskId === taskId) {
        setItems([]);
        setActiveTaskId(null);
        setRunning(false);
        if (currentWorkspace) {
          workspaceCache.current[currentWorkspace] = { items: [], activeTaskId: null, threadId: "", input: "" };
        }
        const url = new URL(window.location.href);
        url.hash = "";
        window.history.replaceState(null, "", url.toString());
      }
      refreshHistory();
    } catch {
      refreshHistory();
    }
  };

  const newChat = () => {
    // 新建对话 = 当前工作区的空会话（缓存同步清空，避免切走切回恢复旧会话）
    if (currentWorkspace) {
      workspaceCache.current[currentWorkspace] = { items: [], activeTaskId: null, threadId: "", input: "" };
    }
    setItems([]);
    setActiveTaskId(null);
    setRunning(false);
    setInput("");
    lastAssistantId.current = null;
    lastToolId.current = null;
    setThreadId(""); // 新会话 = 新线程（由服务端自动生成）
    const url = new URL(window.location.href);
    url.hash = "";
    window.history.replaceState(null, "", url.toString());
  };

  // DSH 对齐：切换工作区 —— 保存当前工作区视图状态，恢复目标工作区缓存（切换不刷没）；
  // 无默认工作区：先选/建工作区，对话从属工作区，会话列表按工作区过滤
  const switchWorkspace = (ws: string) => {
    if (!ws || ws === currentWorkspace) return;
    if (currentWorkspace) {
      // 保存当前工作区的对话视图状态（items/活动会话/线程/草稿）
      workspaceCache.current[currentWorkspace] = { items, activeTaskId, threadId, input };
    }
    const saved = workspaceCache.current[ws];
    if (saved) {
      // 恢复对话视图快照（items/线程/草稿），但不自动重连 SSE——
      // EventSource 整段重放会与已恢复内容重复；想看完整回放可点侧栏会话
      setItems(saved.items);
      setThreadId(saved.threadId);
      setInput(saved.input);
      setActiveTaskId(null);
      setRunning(false);
    } else {
      setItems([]);
      setActiveTaskId(null);
      setThreadId("");
      setInput("");
      setRunning(false);
    }
    setCurrentWorkspace(ws);
    lastAssistantId.current = null;
    lastToolId.current = null;
    const url = new URL(window.location.href);
    url.hash = "";
    window.history.replaceState(null, "", url.toString());
    refreshHistory();
    refreshWorkspaces();
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="flex h-full w-full overflow-hidden">
      <div className="hidden h-full md:block">
        <Sidebar
          tasks={tasks}
          activeTaskId={activeTaskId}
          onPick={pickTask}
          onNew={newChat}
          onDelete={handleDelete}
          running={running}
          view={view}
          onNavigate={setView}
          pendingApprovals={pendingApprovals}
          buildTag={BUILD_TAG}
          workspaces={workspaces}
          currentWorkspace={currentWorkspace}
          onSwitchWorkspace={switchWorkspace}
        />
      </div>
      <main className="flex min-w-0 flex-1 flex-col">
        {view === "chat" ? (
          <>
            <ChatView items={items} running={running} onPick={(t) => send(t)} />
            <Composer
              value={input}
              onChange={setInput}
              onSend={() => send()}
              onStop={cancel}
              onKeyDown={onKeyDown}
              disabled={!currentWorkspace}
              running={running}
            />
          </>
        ) : view === "kb" ? (
          <KnowledgeBaseView />
        ) : view === "memory" ? (
          <MemoryView />
        ) : view === "capabilities" ? (
          <CapabilitiesView />
        ) : view === "api" ? (
          <ApiView />
        ) : view === "approvals" ? (
          <ApprovalsView />
        ) : view === "model" ? (
          <ModelSettingsView />
        ) : (
          <OpsView />
        )}
      </main>
    </div>
  );
}
