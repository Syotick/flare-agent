import { useEffect, useRef, useState } from "react";
import { createTask, deleteTask, getTask, listTasks } from "./api";
import { Composer, Sidebar, renderItem } from "./components";
import type { Item } from "./types";

let nextId = 1;

interface ResultPayload {
  result: {
    status: string;
    output: string;
    step_count: number;
    message_count: number;
  } | null;
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
  const [input, setInput] = useState("");
  const [maxSteps, setMaxSteps] = useState(5);
  const [threadId, setThreadId] = useState("");
  const [running, setRunning] = useState(false);
  const [items, setItems] = useState<Item[]>([]);
  const [tasks, setTasks] = useState<import("./api").TaskDetail[]>([]);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const endRef = useRef<HTMLDivElement | null>(null);
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
      const data = parseSSE<{ type: string; node: string[]; data: Record<string, any> }>(
        (ev as MessageEvent).data
      );
      if (!data) return;
      const nodes = Array.isArray(data.node) ? data.node : [];

      if (nodes.includes("actor") && data.data.actor) {
        const actor = data.data.actor;
        if (actor.action === "call_tool" && actor.pending_tool) {
          const id = nextId++;
          lastToolId.current = id;
          setItems((prev) => [
            ...prev,
            {
              id,
              kind: "tool",
              name: actor.pending_tool.name,
              args: actor.pending_tool.args || {},
              status: "running",
            },
          ]);
        }
        if (actor.action === "final" && actor.output) {
          const id = nextId++;
          lastAssistantId.current = id;
          setItems((prev) => [
            ...prev,
            { id, kind: "assistant", msg: { text: actor.output, done: false } },
          ]);
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
                ? {
                    ...it,
                    status: "done" as const,
                    result: {
                      ok: r.ok,
                      content: r.content,
                      error_code: r.error_code,
                      artifacts: r.artifacts || {},
                    },
                  }
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
          prev.map((it) =>
            it.id === aid && it.kind === "assistant"
              ? { ...it, msg: { ...it.msg, done: true } }
              : it
          )
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
        setItems((prev) => [
          ...prev,
          { id: nextId++, kind: "status", text: "connection lost", tone: "error" },
        ]);
      }
    };

    return () => {
      closed = true;
      window.clearTimeout(stall);
      es.close();
    };
  }, [activeTaskId]);

  // 自动滚底
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [items.length]);

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

  const send = async () => {
    const text = input.trim();
    if (!text || running) return;
    setRunning(true);
    setInput("");
    setItems((prev) => [...prev, { id: nextId++, kind: "user", text }]);
    try {
      const created = await createTask(text, maxSteps, threadId || undefined);
      rememberTask(created.task_id);
      setActiveTaskId(created.task_id);
      setItems((prev) => [
        ...prev,
        {
          id: nextId++,
          kind: "status",
          text: "submitted · " + created.task_id,
          tone: "info",
        },
      ]);
    } catch (err) {
      setRunning(false);
      setItems((prev) => [
        ...prev,
        {
          id: nextId++,
          kind: "status",
          text: err instanceof Error ? err.message : String(err),
          tone: "error",
        },
      ]);
    }
  };

  const cancel = () => {
    setActiveTaskId(null);
    setRunning(false);
    setItems((prev) => [
      ...prev,
      { id: nextId++, kind: "status", text: "cancelled", tone: "warn" },
    ]);
  };

  const pickTask = (taskId: string) => {
    setRunning(true);
    setActiveTaskId(taskId);
    setSidebarOpen(false);
    rememberTask(taskId);
    getTask(taskId)
      .then((d) => {
        if (d.status !== "pending" && d.status !== "running") {
          setRunning(false);
        }
      })
      .catch(() => setRunning(false));
  };

  const handleDelete = async (taskId: string) => {
    try {
      await deleteTask(taskId);
      if (activeTaskId === taskId) {
        // 删除当前会话 → 清空并回到新对话
        setItems([]);
        setActiveTaskId(null);
        setRunning(false);
        const url = new URL(window.location.href);
        url.hash = "";
        window.history.replaceState(null, "", url.toString());
      }
      refreshHistory();
    } catch {
      // 删除失败：静默，刷新列表保持一致
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

  const hasContent = items.length > 0;

  return (
    <div className="app">
      <Sidebar
        tasks={tasks}
        activeTaskId={activeTaskId}
        onPick={pickTask}
        onNew={newChat}
        onDelete={handleDelete}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="main">
        {/* 顶栏 */}
        <header className="header">
          <button className="menu-btn" onClick={() => setSidebarOpen(true)}>
            <span className="menu-lines" />
          </button>
          <div className="header-center">
            <span className="orb" />
            <h1>Flare</h1>
          </div>
          <div className="header-right" />
        </header>

        {/* 对话区 */}
        <div className="chat">
          {!hasContent ? (
            <div className="welcome">
              <div className="welcome-orb" />
              <h2>有什么可以帮你的？</h2>
              <p className="welcome-sub">
                Flare 是一个可上线的 AI Agent 平台。<br />
                给我一个任务，我会思考、调用工具、观察并给出结论。
              </p>
            </div>
          ) : (
            <div className="msgs">
              {items.map((it) => renderItem(it))}
              {running && (
                <div className="thinking">
                  <span className="spinner" />
                  thinking…
                </div>
              )}
              <div ref={endRef} />
            </div>
          )}

          {/* 输入栏 */}
          <Composer
            value={input}
            onChange={setInput}
            onSend={send}
            onStop={cancel}
            onKeyDown={onKeyDown}
            disabled={false}
            running={running}
            maxSteps={maxSteps}
            setMaxSteps={setMaxSteps}
            threadId={threadId}
            setThreadId={setThreadId}
          />
        </div>
      </div>
    </div>
  );
}
