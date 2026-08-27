import { useEffect, useRef, useState } from "react";
import { createTask, deleteTask, getTask, listTasks } from "./api";
import ChatView from "./components/ChatView";
import Composer from "./components/Composer";
import KnowledgeBaseView from "./components/KnowledgeBaseView";
import MemoryView from "./components/MemoryView";
import Sidebar from "./components/Sidebar";
import type { Item } from "./types";

export type ViewId = "chat" | "kb" | "memory";

let nextId = 1;

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

export default function App() {
  const [view, setView] = useState<ViewId>("chat");
  const [input, setInput] = useState("");
  const [maxSteps, setMaxSteps] = useState(5);
  const [threadId, setThreadId] = useState("");
  const [running, setRunning] = useState(false);
  const [items, setItems] = useState<Item[]>([]);
  const [tasks, setTasks] = useState<import("./api").TaskDetail[]>([]);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const lastToolId = useRef<number | null>(null);
  const lastAssistantId = useRef<number | null>(null);

  const refreshHistory = () => {
    listTasks().then(setTasks).catch(() => undefined);
  };

  useEffect(() => {
    refreshHistory();
  }, []);

  // 刷新恢复
  useEffect(() => {
    const hash = window.location.hash.match(/task=([a-f0-9]+)/);
    if (hash) {
      const tid = hash[1];
      setActiveTaskId(tid);
      setRunning(true);
      getTask(tid)
        .then((d) => {
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
      const data = parseSSE<{ type: string; node: string[]; data: Record<string, any> }>((ev as MessageEvent).data);
      if (!data) return;
      const nodes = Array.isArray(data.node) ? data.node : [];
      if (nodes.includes("actor") && data.data.actor) {
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
          const id = nextId++;
          lastAssistantId.current = id;
          setItems((prev) => [...prev, { id, kind: "assistant", msg: { text: actor.output, done: false } }]);
        }
      }
      if (nodes.includes("tool_executor") && data.data.tool_executor) {
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
        setItems((prev) =>
          prev.map((it) => (it.id === aid && it.kind === "assistant" ? { ...it, msg: { ...it.msg, done: true } } : it))
        );
      }
      if (data) {
        setItems((prev) => [
          ...prev,
          {
            id: nextId++,
            kind: "status",
            text: "task " + data.status + (data.result ? " · " + data.result.step_count + " steps" : ""),
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
        setItems((prev) => [...prev, { id: nextId++, kind: "status", text: "connection lost", tone: "error" }]);
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
    setRunning(true);
    setInput("");
    setItems((prev) => [...prev, { id: nextId++, kind: "user", text: content }]);
    try {
      const created = await createTask(content, maxSteps, threadId || undefined);
      rememberTask(created.task_id);
      setActiveTaskId(created.task_id);
      setItems((prev) => [
        ...prev,
        { id: nextId++, kind: "status", text: "submitted · " + created.task_id, tone: "info" },
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
    setItems((prev) => [...prev, { id: nextId++, kind: "status", text: "cancelled", tone: "warn" }]);
  };

  const pickTask = (taskId: string) => {
    setRunning(true);
    setActiveTaskId(taskId);
    rememberTask(taskId);
    getTask(taskId)
      .then((d) => {
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
    setItems([]);
    setActiveTaskId(null);
    setRunning(false);
    setInput("");
    const url = new URL(window.location.href);
    url.hash = "";
    window.history.replaceState(null, "", url.toString());
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
              disabled={false}
              running={running}
              maxSteps={maxSteps}
              setMaxSteps={setMaxSteps}
              threadId={threadId}
              setThreadId={setThreadId}
            />
          </>
        ) : view === "kb" ? (
          <KnowledgeBaseView />
        ) : (
          <MemoryView />
        )}
      </main>
    </div>
  );
}
