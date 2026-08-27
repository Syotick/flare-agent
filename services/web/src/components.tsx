import { useEffect, useState } from "react";
import type { Item, ToolResult } from "./types";
import type { TaskDetail } from "./api";
import {
  IconChevron,
  IconClose,
  IconPlus,
  IconSearch,
  IconSend,
  IconSpark,
  IconStop,
  IconTool,
  IconTrash,
} from "./icons";

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

// 助手消息（带流式 + 品牌头像）
export function AssistantBubble({ text, done }: { text: string; done: boolean }) {
  return (
    <div className="row assistant">
      <div className="avatar">
        <IconSpark size={14} />
      </div>
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
            <IconTool size={14} />
          </span>
          <code>{name}</code>
          <span className={"tool-tag " + (ok ? "ok" : "err")}>
            {status === "running" ? "running" : ok ? result?.error_code || "done" : result?.error_code || "error"}
          </span>
          <span className={"chev" + (open ? " open" : "")}>
            <IconChevron dir="down" size={13} />
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

// ===== 会话侧边栏（WorkBuddy 式：搜索 / 日期分组 / 切换 / 删除） =====

function relTime(ts: number): string {
  const ms = Date.now() - ts * 1000;
  if (ms < 60000) return "刚刚";
  if (ms < 3600000) return Math.floor(ms / 60000) + " 分钟前";
  if (ms < 86400000) return Math.floor(ms / 3600000) + " 小时前";
  const d = new Date(ts * 1000);
  return d.getMonth() + 1 + "/" + d.getDate();
}

function groupByDate(tasks: TaskDetail[]): { label: string; items: TaskDetail[] }[] {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const day = 86400000;
  const buckets: [string, (t: TaskDetail) => boolean][] = [
    ["今天", (t) => t.created_at >= start],
    ["昨天", (t) => t.created_at >= start - day && t.created_at < start],
    ["近 7 天", (t) => t.created_at >= start - 7 * day && t.created_at < start - day],
    ["更早", (t) => t.created_at < start - 7 * day],
  ];
  const out: { label: string; items: TaskDetail[] }[] = [];
  for (const [label, pred] of buckets) {
    const items = tasks.filter(pred);
    if (items.length > 0) out.push({ label, items });
  }
  return out;
}

export function Sidebar(props: {
  tasks: TaskDetail[];
  activeTaskId: string | null;
  onPick: (taskId: string) => void;
  onNew: () => void;
  onDelete: (taskId: string) => void;
  open: boolean;
  onClose: () => void;
}) {
  const { tasks, activeTaskId, onPick, onNew, onDelete, open, onClose } = props;
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const filtered = q
    ? tasks.filter((t) => (t.task_input || "").toLowerCase().indexOf(q) >= 0)
    : tasks;
  const groups = groupByDate(filtered);
  return (
    <>
      {open && <div className="sidebar-overlay" onClick={onClose} />}
      <div className={"sidebar" + (open ? " open" : "")}>
        <div className="sidebar-header">
          <span className="sidebar-title">会话</span>
          <button className="sidebar-close" onClick={onClose} title="关闭侧栏">
            <IconClose size={15} />
          </button>
        </div>
        <div className="sidebar-actions">
          <button className="new-chat" onClick={onNew}>
            <IconPlus size={14} />
            <span>新对话</span>
          </button>
          <div className="sidebar-search">
            <span className="search-ico">
              <IconSearch size={13} />
            </span>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索会话…"
            />
            {query && (
              <button className="search-clear" onClick={() => setQuery("")} title="清除">
                <IconClose size={12} />
              </button>
            )}
          </div>
        </div>
        <div className="sidebar-list">
          {filtered.length === 0 && (
            <div className="sidebar-empty">
              {tasks.length === 0 ? "还没有会话，发起一个任务吧" : "没有匹配的会话"}
            </div>
          )}
          {groups.map((g) => (
            <div key={g.label} className="group">
              <div className="group-label">{g.label}</div>
              {g.items.map((t) => (
                <div
                  key={t.task_id}
                  className={"sidebar-item" + (t.task_id === activeTaskId ? " active" : "")}
                  onClick={() => onPick(t.task_id)}
                >
                  <div className="si-title">{t.task_input}</div>
                  <div className="si-meta">
                    <span className={"si-dot " + t.status} />
                    <span className="si-status">{t.status}</span>
                    <span className="si-time">{relTime(t.created_at)}</span>
                    <button
                      className="si-del"
                      title="删除会话"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete(t.task_id);
                      }}
                    >
                      <IconTrash size={13} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
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
              <IconStop size={13} />
              <span>停止</span>
            </button>
          ) : (
            <button
              className="btn-send"
              disabled={disabled || !value.trim()}
              onClick={onSend}
              title="发送 (Enter)"
            >
              <IconSend size={15} />
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
