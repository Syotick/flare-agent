import { useEffect, useState } from "react";
import type { Item, ToolResult } from "./types";
import type { TaskDetail } from "./api";

// 打字机流式文本
export function StreamText({ text, done }: { text: string; done: boolean }) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    setShown(0);
  }, [text]);
  useEffect(() => {
    if (done || shown >= text.length) return;
    const t = window.setTimeout(() => setShown((s) => Math.min(s + 2, text.length)), 12);
    return () => window.clearTimeout(t);
  }, [shown, done, text]);
  return (
    <span>
      {text.slice(0, shown)}
      {!done && <span className="cursor" />}
    </span>
  );
}

// 用户消息
export function UserBubble({ text }: { text: string }) {
  return (
    <div className="row user">
      <div className="bubble user-bubble">{text}</div>
    </div>
  );
}

// 助手消息（带流式）
export function AssistantBubble({ text, done }: { text: string; done: boolean }) {
  return (
    <div className="row assistant">
      <div className="bubble assistant-bubble">
        <StreamText text={text} done={done} />
      </div>
    </div>
  );
}

// 工具调用卡（Codex 风格：简洁、可折叠）
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
  const ok = result ? result.ok : true;
  return (
    <div className="row tool-row">
      <div className="toolblock">
        <button className="tool-btn" onClick={() => setOpen(!open)}>
          <span className="tool-icon">
            {!open ? "⚙" : open ? "▼" : "⚙"}
          </span>
          <code>{name}</code>
          <span className={"tool-tag " + (ok ? "ok" : "err")}>
            {status === "running" ? "running" : ok ? result?.error_code || "done" : result?.error_code || "error"}
          </span>
        </button>
        {open && (
          <div className="tool-detail">
            <div className="tool-kv">
              <span className="tool-kv-key">args</span>
              <pre>{JSON.stringify(args, null, 2)}</pre>
            </div>
            {result && (
              <div className="tool-kv">
                <span className="tool-kv-key">output</span>
                <pre className={ok ? "" : "err"}>{result.content}</pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// 状态行
export function StatusLine({ text, tone }: { text: string; tone: "info" | "warn" | "error" }) {
  return <div className={"sys " + tone}>{text}</div>;
}

// 渲染入口
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

// 左侧边栏（历史任务 — 仿 DeepSeek 对话列表）
export function Sidebar(props: {
  tasks: TaskDetail[];
  activeTaskId: string | null;
  onPick: (taskId: string) => void;
  onNew: () => void;
  open: boolean;
  onClose: () => void;
}) {
  const { tasks, activeTaskId, onPick, onNew, open, onClose } = props;
  return (
    <>
      {open && <div className="sidebar-overlay" onClick={onClose} />}
      <div className={"sidebar" + (open ? " open" : "")}>
        <div className="sidebar-header">
          <button className="new-chat" onClick={onNew}>
            ＋ 新对话
          </button>
          <button className="sidebar-close" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="sidebar-list">
          {tasks.length === 0 && <div className="sidebar-empty">还没有任务</div>}
          {tasks.map((t) => (
            <button
              key={t.task_id}
              className={"sidebar-item" + (t.task_id === activeTaskId ? " active" : "")}
              onClick={() => onPick(t.task_id)}
            >
              <div className="si-title">{t.task_input}</div>
              <div className="si-meta">
                <span className={"si-dot " + t.status} />
                {t.status}
              </div>
            </button>
          ))}
        </div>
      </div>
    </>
  );
}

// 底部输入栏（仿 DeepSeek：简洁、固定底部、Enter 发送）
export function Composer(props: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  onStop: () => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  disabled: boolean;
  running: boolean;
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
      <div className="composer-box">
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="给 Flare 发一个任务…"
          rows={1}
          disabled={disabled}
        />
        <div className="composer-bar">
          <div className="composer-left">
            <span className="hint">Enter 发送 · Shift+Enter 换行</span>
          </div>
          {running ? (
            <button className="btn-stop" onClick={onStop}>
              ■ 停止
            </button>
          ) : (
            <button className="btn-send" disabled={disabled || !value.trim()} onClick={onSend}>
              ▶
            </button>
          )}
        </div>
      </div>
      <div className="composer-opts">
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
          thread_id
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
