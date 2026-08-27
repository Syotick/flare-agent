import { useRef, useState } from "react";
import { createTask, type TaskCreated } from "./api";

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

export default function App() {
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [task, setTask] = useState<TaskCreated | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const run = async () => {
    const text = input.trim();
    if (!text || running) return;
    setRunning(true);
    setEntries([]);
    setTask(null);
    try {
      const created = await createTask(text);
      setTask(created);
      const es = new EventSource("/v1/tasks/" + created.task_id + "/stream");
      esRef.current = es;
      es.addEventListener("step", (ev) => {
        const data = JSON.parse((ev as MessageEvent).data) as StepEvent;
        for (const node of data.node) {
          setEntries((prev) => [...prev, { kind: "step", node, payload: data }]);
        }
      });
      es.addEventListener("result", (ev) => {
        const data = JSON.parse((ev as MessageEvent).data) as ResultPayload;
        setEntries((prev) => [...prev, { kind: "result", payload: data }]);
        es.close();
        esRef.current = null;
        setRunning(false);
      });
      es.onerror = () => {
        es.close();
        esRef.current = null;
        setRunning(false);
      };
    } catch (err) {
      setEntries((prev) => [
        ...prev,
        { kind: "error", message: err instanceof Error ? err.message : String(err) },
      ]);
      setRunning(false);
    }
  };

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">✦</span>
          <h1>Flare Agent</h1>
          <span className="tag">Agent Console</span>
        </div>
        <div className="meta">
          {task && (
            <span className="pill">
              task {task.task_id} · thread {task.thread_id}
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
            disabled={running}
          />
          <div className="actions">
            <button className="run" onClick={run} disabled={running || !input.trim()}>
              {running ? "执行中…" : "▶ 运行"}
            </button>
          </div>
        </section>

        <section className="timeline">
          {entries.length === 0 && !running && (
            <div className="empty">提交任务后，Agent 的执行轨迹会实时显示在这里。</div>
          )}
          {entries.map((entry, i) =>
            entry.kind === "step" ? (
              <StepCard key={i} node={entry.node} payload={entry.payload} />
            ) : entry.kind === "result" ? (
              <ResultCard key={i} payload={entry.payload} />
            ) : (
              <div key={i} className="card error">
                <span className="badge err">错误</span>
                <pre>{entry.message}</pre>
              </div>
            )
          )}
        </section>
      </main>

      <footer className="foot">
        Flare Agent · M2-4e Web shell · mock 模型供应商 · SQLite checkpoint
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
          <pre className="json">{JSON.stringify(tool.args, null, 2)}</pre>
        </div>
      );
    }
    return (
      <div className="card step">
        <div className="head">
          <span className="badge actor">actor</span>
          <span className="title">给出结论</span>
        </div>
        <pre className="json">{JSON.stringify(data.output ?? "", null, 2)}</pre>
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
        <pre className={"json " + (ok ? "" : "err")}>{r?.content ?? "(无内容)"}</pre>
      </div>
    );
  }
  return (
    <div className="card step">
      <div className="head">
        <span className="badge">{node}</span>
        <span className="title">节点输出</span>
      </div>
      <pre className="json">{JSON.stringify(data, null, 2)}</pre>
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
      <pre className="out">{payload.result?.output ?? payload.error ?? "(无输出)"}</pre>
      {payload.result && (
        <div className="stats">
          <span>步骤 {payload.result.step_count}</span>
          <span>消息 {payload.result.message_count}</span>
        </div>
      )}
    </div>
  );
}
