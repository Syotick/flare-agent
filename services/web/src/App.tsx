import { useEffect, useRef, useState } from "react";
import {
  createTask,
  getTask,
  listTasks,
  type TaskCreated,
  type TaskDetail,
} from "./api";

interface StepEvent {
  type: string;
  node: string[];
  data: Record<string, any>;
}

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

type Entry =
  | { kind: "step"; node: string; payload: StepEvent }
  | { kind: "result"; payload: ResultPayload }
  | { kind: "error"; message: string };

const STALL_TIMEOUT_MS = 30000;
const MAX_INPUT = 10000;
const FOLD_THRESHOLD = 2000;

function parseSSE<T>(raw: string): T | null {
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function code(taskId: string): string {
  return "/v1/tasks/" + taskId + "/stream";
}

export default function App() {
  const [input, setInput] = useState("");
  const [maxSteps, setMaxSteps] = useState(5);
  const [threadId, setThreadId] = useState("");
  const [running, setRunning] = useState(false);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [task, setTask] = useState<TaskCreated | null>(null);
  const [tasks, setTasks] = useState<TaskDetail[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  const refreshHistory = () => {
    listTasks().then(setTasks).catch(() => undefined);
  };

  // L3: 历史入口
  useEffect(() => {
    refreshHistory();
  }, []);

  // 问题3: 刷新后从 URL #task= 恢复，重连 SSE
  useEffect(() => {
    const hash = window.location.hash.match(/task=([a-f0-9]+)/);
    const saved = hash ? hash[1] : null;
    if (saved) {
      setActiveTaskId(saved);
      setRunning(true);
      getTask(saved)
        .then((d) => {
          setTask({ task_id: d.task_id, thread_id: d.thread_id, status: d.status });
          if (d.status !== "pending" && d.status !== "running") setRunning(false);
        })
        .catch(() => undefined);
    }
  }, []);

  // L2: SSE 生命周期由 effect 管理——卸载/切换/取消自动 close
  useEffect(() => {
    if (!activeTaskId) return;
    let finished = false;
    let closed = false;
    const es = new EventSource(code(activeTaskId));
    let stall = window.setTimeout(() => {
      es.close();
      setError("SSE 超时：长时间未收到事件，已断开");
      setRunning(false);
    }, STALL_TIMEOUT_MS);

    const resetStall = () => {
      window.clearTimeout(stall);
      stall = window.setTimeout(() => {
        es.close();
        setError("SSE 超时：长时间未收到事件，已断开");
        setRunning(false);
      }, STALL_TIMEOUT_MS);
    };

    es.addEventListener("step", (ev) => {
      resetStall();
      // L4: 流事件防御——解析失败/字段异常不崩回调
      const data = parseSSE<StepEvent>((ev as MessageEvent).data);
      if (!data) return;
      const nodes = Array.isArray(data.node) ? data.node : [];
      if (nodes.length === 0) return;
      const steps: Entry[] = nodes.map((n) => ({
        kind: "step" as const,
        node: n,
        payload: data,
      }));
      setEntries((prev) => [...prev, ...steps]);
    });

    es.addEventListener("result", (ev) => {
      finished = true;
      const data = parseSSE<ResultPayload>((ev as MessageEvent).data);
      window.clearTimeout(stall);
      es.close();
      setRunning(false);
      if (data) setEntries((prev) => [...prev, { kind: "result", payload: data }]);
      refreshHistory();
    });

    es.onerror = () => {
      window.clearTimeout(stall);
      es.close();
      setRunning(false);
      if (!closed && !finished) setError("SSE 连接中断");
    };

    return () => {
      closed = true;
      window.clearTimeout(stall);
      es.close();
    };
  }, [activeTaskId]);

  // 问题2: 新事件后自动滚底
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [entries]);

  const saveTaskRef = (taskId: string) => {
    const url = new URL(window.location.href);
    url.hash = "#task=" + taskId;
    window.history.replaceState(null, "", url.toString());
    try {
      localStorage.setItem("flare.lastTaskId", taskId);
    } catch {
      // 隐私模式等场景忽略
    }
  };

  const run = async () => {
    const text = input.trim();
    if (!text || running) return;
    setRunning(true);
    setEntries([]);
    setError(null);
    setTask(null);
    try {
      const created = await createTask(text, maxSteps, threadId || undefined);
      setTask(created);
      saveTaskRef(created.task_id);
      setActiveTaskId(created.task_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setRunning(false);
    }
  };

  const cancel = () => {
    setActiveTaskId(null); // effect cleanup 负责 close SSE
    setRunning(false);
    setError("已取消");
  };

  const attach = (taskId: string) => {
    setRunning(true);
    setEntries([]);
    setError(null);
    setActiveTaskId(taskId);
    saveTaskRef(taskId);
    getTask(taskId)
      .then((d) => {
        setTask({ task_id: d.task_id, thread_id: d.thread_id, status: d.status });
        if (d.status !== "pending" && d.status !== "running") setRunning(false);
      })
      .catch(() => undefined);
  };

  const statusText = running ? "执行中" : task ? task.status : "空闲";

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">✦</span>
          <h1>Flare Agent</h1>
          <span className="tag">Agent Console</span>
        </div>
        <div className="meta">
          {activeTaskId && (
            <span className="pill">
              task {activeTaskId} · {statusText}
            </span>
          )}
        </div>
      </header>

      <main>
        <section className="composer">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="描述一个任务，例如：帮我 echo 一句问候语…"
            rows={3}
            maxLength={MAX_INPUT}
            disabled={running}
          />
          <div className="controls">
            <label>
              最大步骤
              <input
                type="number"
                min={1}
                max={50}
                value={maxSteps}
                onChange={(e) => setMaxSteps(Number(e.target.value) || 5)}
                disabled={running}
              />
            </label>
            <label>
              thread_id（续跑同会话，可选）
              <input
                type="text"
                value={threadId}
                onChange={(e) => setThreadId(e.target.value)}
                placeholder="留空自动生成"
                disabled={running}
              />
            </label>
            <span className="spacer" />
            {running ? (
              <button className="cancel" onClick={cancel}>
                ■ 取消
              </button>
            ) : (
              <button className="run" onClick={run} disabled={!input.trim()}>
                ▶ 运行
              </button>
            )}
          </div>
        </section>

        {error && (
          <div className="card error">
            <span className="badge err">提示</span>
            <pre className="err">{error}</pre>
          </div>
        )}

        <div className="columns">
          <section className="timeline">
            {entries.length === 0 && !running && (
              <div className="empty">提交任务后，Agent 的执行轨迹会实时显示在这里。</div>
            )}
            {entries.length === 0 && running && (
              <div className="empty">任务已提交，等待 Agent 执行…</div>
            )}
            {entries.map((entry, i) =>
              entry.kind === "step" ? (
                <StepCard key={i} node={entry.node} payload={entry.payload} />
              ) : entry.kind === "result" ? (
                <ResultCard key={i} payload={entry.payload} />
              ) : (
                <div key={i} className="card error">
                  <span className="badge err">错误</span>
                  <pre className="err">{entry.message}</pre>
                </div>
              )
            )}
            <div ref={endRef} className="end" />
          </section>

          <aside className="history">
            <div className="history-title">最近任务</div>
            {tasks.length === 0 && <div className="history-empty">暂无</div>}
            {tasks.map((t) => (
              <button
                key={t.task_id}
                className={"hist-item" + (t.task_id === activeTaskId ? " active" : "")}
                onClick={() => attach(t.task_id)}
              >
                <div className="hist-line1">
                  <span className={"dot " + t.status}>{t.status}</span>
                  <span className="hist-id">{t.task_id}</span>
                </div>
                <div className="hist-input">{t.task_input}</div>
              </button>
            ))}
          </aside>
        </div>
      </main>

      <footer className="foot">
        Flare Agent · mock 模型供应商 · SQLite checkpoint · SSE 实时流
      </footer>
    </div>
  );
}

function StepCard({ node, payload }: { node: string; payload: StepEvent }) {
  const data = payload.data[node];
  if (node === "actor") {
    const tool = data.pending_tool;
    if (data.action === "call_tool" && tool) {
      return (
        <div className="card step">
          <div className="head">
            <span className="badge actor">actor</span>
            <span className="title">决定调用工具</span>
            <code className="tool-name">{tool.name}</code>
          </div>
          <CodeBlock text={JSON.stringify(tool.args, null, 2)} />
        </div>
      );
    }
    return (
      <div className="card step">
        <div className="head">
          <span className="badge actor">actor</span>
          <span className="title">给出结论</span>
        </div>
        <CodeBlock text={JSON.stringify(data.output ?? "", null, 2)} />
      </div>
    );
  }
  if (node === "tool_executor") {
    const r = data.last_tool_result;
    const ok = r?.ok !== false;
    return (
      <div className="card step">
        <div className="head">
          <span className="badge tool">tool_executor</span>
          <span className="title">执行结果</span>
          {r?.error_code && <code className="err-code">{r.error_code}</code>}
        </div>
        <CodeBlock text={r?.content ?? "(无内容)"} className={"json" + (ok ? "" : " err")} />
      </div>
    );
  }
  return (
    <div className="card step">
      <div className="head">
        <span className="badge">{node}</span>
        <span className="title">节点输出</span>
      </div>
      <CodeBlock text={JSON.stringify(data, null, 2)} />
    </div>
  );
}

function ResultCard({ payload }: { payload: ResultPayload }) {
  const s = payload.status;
  const ok = s === "completed";
  return (
    <div className={"card result " + (ok ? "ok" : "warn")}>
      <div className="head">
        <span className="badge result">result</span>
        <span className="title">任务结束 · {s}</span>
      </div>
      <CodeBlock
        text={payload.result?.output ?? payload.error ?? "(无输出)"}
        className="out"
      />
      {payload.result && (
        <div className="stats">
          <span>步骤 {payload.result.step_count}</span>
          <span>消息 {payload.result.message_count}</span>
        </div>
      )}
    </div>
  );
}

function CodeBlock({ text, className = "json" }: { text: string; className?: string }) {
  const [open, setOpen] = useState(false);
  const long = text.length > FOLD_THRESHOLD;
  const shown = long && !open ? text.slice(0, FOLD_THRESHOLD) + "…(已截断)" : text;
  return (
    <div className="codeblock">
      <pre className={className}>{shown}</pre>
      {long && (
        <button className="fold" onClick={() => setOpen(!open)}>
          {open ? "收起" : "展开全文 (" + text.length + " 字符)"}
        </button>
      )}
    </div>
  );
}
