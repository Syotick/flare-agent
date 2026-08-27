import { useState } from "react";
import { Hash, Send, Square, Zap } from "lucide-react";
import { cn } from "../lib/utils";

export default function Composer(props: {
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
    value, onChange, onSend, onStop, onKeyDown,
    running, maxSteps, setMaxSteps, threadId, setThreadId,
  } = props;
  const [focused, setFocused] = useState(false);

  return (
    <div className="mx-auto w-full max-w-[860px] flex-none px-6 pb-6 pt-2.5">
      <div
        className={cn(
          "flex flex-col gap-2.5 rounded-2xl border bg-card/80 p-4 pb-3 shadow-card backdrop-blur-xl transition-all",
          focused && "border-primary/45 shadow-glow",
          running && "border-primary/40 shadow-glow"
        )}
      >
        {/* 工具栏：参数行（与同类产品一致，输入框上方） */}
        <div className="flex flex-wrap items-center gap-2 px-1">
          <label className="flex cursor-pointer items-center gap-1.5 rounded-lg border border-border bg-input px-2 py-1" title="Agent 最大思考→行动步骤数">
            <Zap className="h-3 w-3 flex-none text-muted-foreground" />
            <select
              value={maxSteps}
              disabled={running}
              onChange={(e) => setMaxSteps(Number(e.target.value))}
              className="bg-transparent text-[11px] text-muted-foreground outline-none disabled:cursor-not-allowed [&>option]:bg-card [&>option]:text-foreground"
            >
              {[1, 2, 3, 4, 5, 6, 8, 10, 15, 20].map((n) => (
                <option key={n} value={n}>max {n} 步</option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-1.5 rounded-lg border border-border bg-input px-2 py-1" title="thread_id：同一会话延续上下文（可留空自动生成）">
            <Hash className="h-3 w-3 flex-none text-muted-foreground" />
            <input
              value={threadId}
              disabled={running}
              onChange={(e) => setThreadId(e.target.value)}
              placeholder="thread_id"
              autoComplete="off"
              className="w-40 bg-transparent text-[11px] text-muted-foreground outline-none placeholder:text-muted-foreground/70 disabled:cursor-not-allowed"
            />
          </label>
        </div>

        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={running ? "正在执行…" : "给 Flare 发一个任务，Enter 发送，Shift+Enter 换行"}
          disabled={running}
          autoComplete="off"
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onKeyDown={onKeyDown}
          className="max-h-[180px] min-h-[44px] w-full resize-y border-none bg-transparent px-1 py-1.5 text-sm leading-relaxed text-foreground outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
        />

        <div className="flex items-center justify-end gap-2.5">
          <span className="mr-auto text-[11px] text-muted-foreground">
            {!running && value && "Enter 发送 · Shift+Enter 换行"}
          </span>
          {running ? (
            <button
              className="flex items-center gap-2 rounded-xl border border-destructive/40 bg-destructive/10 px-5 py-2 text-[13px] font-semibold text-destructive transition-all hover:scale-[1.03] hover:bg-destructive/20"
              onClick={onStop}
            >
              <Square className="h-2.5 w-2.5 fill-current" />
              停止
            </button>
          ) : (
            <button
              className="gradient-flare flex items-center gap-2 rounded-xl px-5 py-2 text-[13px] font-semibold text-white shadow-[0_3px_16px_rgba(255,122,60,0.35)] transition-all hover:-translate-y-px hover:brightness-110 active:translate-y-0 disabled:pointer-events-none disabled:opacity-40"
              disabled={!value.trim()}
              onClick={onSend}
            >
              发送
              <Send className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
