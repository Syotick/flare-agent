import { useEffect, useRef, useState } from "react";
import { createTask, getTask, listTasks } from "./api";
import { Composer, SidePanel, renderItem } from "./components";
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
  const [statusText, setStatusText] = useState("空闲");
  const endRef = useRef<HTMLDivElement | null>(null);
  const lastToolId = useRef<number | null>(null);
  const lastAssistantId = useRef<number | null>(null);

  const refreshHistory = () => {
    listTasks().then(setTasks).catch(() => undefined);
  };

  useEffect(() => {
    refreshHistory();
  }, []);

  // 刷新恢复：从 URL #task= 重连
  useEffect(() => {
    const hash = window.location.hash.match(/task=([a-f0-9]+)/);
    if (hash) {
      const tid = hash[1];
      setActiveTaskId(tid);
      setRunning(true);
      setStatusText("正在恢复会话…");
      getTask(tid)
        .then((d) => {
          if (d.status !== "pending" && d.status !== "running") {
            setRunning(false);
            setStatusText(d.status);
          }
        })
        .catch(() => setRunning(false));
    }
  }, []);

  // SSE 生命周期（卸载/切换自动 close）
  useEffect(() => {
    if (!activeTaskId) return;
    let finished = false;
    let closed = false;
    const es = new EventSource(streamUrl(activeTaskId));
    const stall = window.setTimeout(() => {
      es.close();
      setRunning(false);
      setStatusText("连接超时");
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
        const tone: "info" | "warn" | "error" =
          data.status === "completed" ? "info" : data.status === "failed" ? "error" : "warn";
        const msg =
          "任务结束 · " +
          data.status +
          (data.result ? " · 步骤 " + data.result.step_count : data.error ? " · " + data.error : "");
        setItems((prev) => [...prev, { id: nextId++, kind: "status", text: msg, tone }]);
      }
      es.close();
      setRunning(false);
      setStatusText(data?.status ?? "结束");
      refreshHistory();
    });

    es.onerror = () => {
      window.clearTimeout(stall);
      es.close();
      setRunning(false);
      if (!closed && !finished) {
        setStatusText("连接中断");
        setItems((prev) => [
          ...prev,
          { id: nextId++, kind: "status", text: "SSE 连接中断", tone: "error" },
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
    setStatusText("提交中…");
    try {
      const created = await createTask(text, maxSteps, threadId || undefined);
      setStatusText("运行中 · " + created.task_id);
      rememberTask(created.task_id);
      setActiveTaskId(created.task_id);
      setItems((prev) => [
        ...prev,
        {
          id: nextId++,
          kind: "status",
          text: "已提交 · task " + created.task_id + " · 后台执行中",
          tone: "info",
        },
      ]);
    } catch (err) {
      setRunning(false);
      setStatusText("提交失败");
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
    setStatusText("已取消");
    setItems((prev) => [
      ...prev,
      { id: nextId++, kind: "status", text: "已取消", tone: "warn" },
    ]);
  };

  const pickTask = (taskId: string) => {
    setRunning(true);
    setStatusText("正在加载 " + taskId);
    setActiveTaskId(taskId);
    rememberTask(taskId);
    getTask(taskId)
      .then((d) => {
        if (d.status !== "pending" && d.status !== "running") {
          setRunning(false);
          setStatusText(d.status);
        }
      })
      .catch(() => setRunning(false));
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="orb" />
          <h1>Flare</h1>
          <span className="tag">Agent Console</span>
        </div>
        <div className="meta">
          {activeTaskId && (
            <span className="pill">
              <span className={"pdot " + (running ? "running" : "idle")} />
              {statusText}
            </span>
          )}
        </div>
      </header>

      <div className="body">
        <main className="chatarea">
          <div className="messages">
            {items.length === 0 && (
              <div className="welcome">
                <div className="welcome-orb" />
                <div className="welcome-title">你好，我是 Flare</div>
                <div className="welcome-sub">
                  一个可上线的 AI Agent 平台。给我一个任务，我会思考、调用工具、观察并给出结论。
                </div>
                <div className="welcome-hints">
                  <span>试试：帮我 echo 一句问候语</span>
                  <span>工具调用会以内联卡片展示</span>
                </div>
              </div>
            )}
            {items.map((it) => renderItem(it))}
            {running && items.length > 0 && (
              <div className="thinking">
                <span className="spinner" />
                <span>执行中…</span>
              </div>
            )}
            <div ref={endRef} />
          </div>
          <Composer
            value={input}
            onChange={setInput}
            onSend={send}
            onStop={cancel}
            onKeyDown={onKeyDown}
            disabled={running}
            running={running}
            maxSteps={maxSteps}
            setMaxSteps={setMaxSteps}
            threadId={threadId}
            setThreadId={setThreadId}
          />
        </main>
        <SidePanel tasks={tasks} activeTaskId={activeTaskId} onPick={pickTask} />
      </div>
    </div>
  );
}
