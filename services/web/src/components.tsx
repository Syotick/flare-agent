import { useEffect, useState } from "react";
import type { Item, ToolResult } from "./types";
import type { TaskDetail } from "./api";

export function StreamText({ text, done }: { text: string; done: boolean }) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    setShown(0);
  }, [text]);
  useEffect(() => {
    if (done || shown >= text.length) return;
    const t = window.setTimeout(() => setShown((s) => Math.min(s + 2, text.length)), 16);
    return () => window.clearTimeout(t);
  }, [shown, done, text]);
  return (
    <span>
      {text.slice(0, shown)}
      {!done && <span className="cursor" />}
    </span>
  );
}

export function UserBubble({ text }: { text: string }) {
  return <div className="row user"><div className="bubble user-bubble">{text}</div></div>;
}

export function AssistantBubble({ text, done }: { text: string; done: boolean }) {
  return (
    <div className="row assistant">
      <div className="avatar">✦</div>
      <div className="bubble assistant-bubble">
        <StreamText text={text} done={done} />
      </div>
    </div>
  );
}

export function ToolCard({
  name,
  args,
  status,
  result,
}: {
  name: string;
  args: Record<string, unknown>;
  status: "running" | "done";
  result?: ToolResult;
}) {
  const [open, setOpen] = useState(false);
  const done = status === "done";
  const ok = result ? result.ok : !done;
  return (
    <div className={"row tool-row"}>
      <div className="toolcard">
        <button className="tool-head" onClick={() => setOpen(!open)}>
          <span className={"dot " + status} />
          <code className="tool-name">{name}</code>
          <span className={"tool-status " + (ok ? "ok" : "err")}>
            {!done ? "运行中" : ok ? "完成" : result?.error_code ?? "失败"}
          </span>
          <span className="chev">{open ? "▾" : "▸"}</span>
        </button>
        {open && (
          <div className="tool-body">
            <div className="tool-label">参数</div>
            <pre>{JSON.stringify(args, null, 2)}</pre>
            {result && (
              <>
                <div className="tool-label">结果</div>
                <pre className={ok ? "" : "err"}>{result.content}</pre>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function StatusLine({ text, tone }: { text: string; tone: "info" | "warn" | "error" }) {
  return <div className={"status-line " + tone}>{text}</div>;
}

export function Composer(props: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  disabled: boolean;
  running: boolean;
  onStop: () => void;
  maxSteps: number;
  setMaxSteps: (n: number) => void;
  threadId: string;
  setThreadId: (s: string) => void;
}) {
  const {
    value,
    onChange,
    onSend,
    onStop,
    onKeyDown,
    disabled,
    running,
    maxSteps,
    setMaxSteps,
    threadId,
    setThreadId,
  } = props;
  return (
    <div className="composer">
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder="向 Flare Agent 发一个任务…"
        rows={2}
        disabled={disabled}
      />
      <div className="composer-bar">
        <span className="composer-hint">Enter 发送 · Shift+Enter 换行</span>
        {running ? (
          <button className="send stop" onClick={onStop}>
            停止
          </button>
        ) : (
          <button className="send" disabled={disabled || !value.trim()} onClick={onSend}>
            发送
          </button>
        )}
      </div>
      <div className="params">
        <label>
          最大步骤
          <input
            type="number"
            min={1}
            max={50}
            value={maxSteps}
            onChange={(e) => setMaxSteps(Number(e.target.value) || 5)}
            disabled={disabled}
          />
        </label>
        <label>
          thread_id 会话
          <input
            type="text"
            value={threadId}
            onChange={(e) => setThreadId(e.target.value)}
            placeholder="留空自动生成"
            disabled={disabled}
          />
        </label>
      </div>
    </div>
  );
}

export function SidePanel(props: {
  tasks: TaskDetail[];
  activeTaskId: string | null;
  onPick: (taskId: string) => void;
}) {
  const { tasks, activeTaskId, onPick } = props;
  return (
    <aside className="sidepanel">
      <div className="side-title">最近任务</div>
      {tasks.length === 0 && <div className="side-empty">暂无任务</div>}
      {tasks.map((t) => (
        <button
          key={t.task_id}
          className={"hist-item" + (t.task_id === activeTaskId ? " active" : "")}
          onClick={() => onPick(t.task_id)}
        >
          <div className="hist-line1">
            <span className={"dot " + t.status}>{t.status}</span>
            <span className="hist-id">{t.task_id}</span>
          </div>
          <div className="hist-input">{t.task_input}</div>
        </button>
      ))}
    </aside>
  );
}

export function renderItem(it: Item) {
  switch (it.kind) {
    case "user":
      return <UserBubble key={it.id} text={it.text} />;
    case "assistant":
      return <AssistantBubble key={it.id} text={it.msg.text} done={it.msg.done} />;
    case "tool":
      return (
        <ToolCard
          key={it.id}
          name={it.name}
          args={it.args}
          status={it.status}
          result={it.result}
        />
      );
    case "status":
      return <StatusLine key={it.id} text={it.text} tone={it.tone} />;
  }
}
