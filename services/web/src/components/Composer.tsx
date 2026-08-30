import { useState } from "react";
import { Send, Square } from "lucide-react";
import { cn } from "../lib/utils";

export default function Composer(props: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  onStop: () => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  disabled: boolean;
  running: boolean;
}) {
  const { value, onChange, onSend, onStop, onKeyDown, disabled, running } = props;
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
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={disabled ? "请先选择或创建工作区，再开始对话" : running ? "正在执行…" : "给 Flare 发个任务…"}
          disabled={running || disabled}
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
              disabled={!value.trim() || disabled}
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
