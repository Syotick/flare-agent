import { useRef, useState } from "react";
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
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  // 自动增高：内容变化时按 scrollHeight 撑高（上限 180px）
  const autoGrow = () => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 180) + "px";
  };

  return (
    <div className="mx-auto w-full max-w-[860px] flex-none px-6 pb-6 pt-2.5">
      <div
        className={cn(
          "flex flex-col gap-2.5 rounded-2xl border bg-card/80 p-4 pb-3 shadow-card backdrop-blur-xl transition-all duration-200",
          focused && "border-primary/50 shadow-glow",
          running && "border-primary/40 shadow-glow"
        )}
      >
        <textarea
          ref={taRef}
          value={value}
          onChange={(e) => { onChange(e.target.value); autoGrow(); }}
          placeholder={disabled ? "请先选择或创建工作区，再开始对话" : running ? "正在执行…" : "给 Flare 发个任务…"}
          disabled={running || disabled}
          autoComplete="off"
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          onKeyDown={onKeyDown}
          className="max-h-[180px] min-h-[44px] w-full resize-none border-none bg-transparent px-1 py-1.5 text-sm leading-relaxed text-foreground outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
        />

        <div className="flex items-center justify-end gap-3">
          <span className="mr-auto text-[11px] text-muted-foreground/80">
            {!running && value && "Enter 发送 · Shift+Enter 换行"}
          </span>
          {running ? (
            <button
              className="flex items-center gap-2 rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-2 text-[13px] font-semibold text-destructive transition-all duration-200 hover:scale-[1.03] hover:bg-destructive/20"
              onClick={onStop}
            >
              <Square className="h-2.5 w-2.5 fill-current" />
              停止
            </button>
          ) : (
            <button
              className="gradient-flare group flex h-9 items-center gap-2 rounded-full px-4 text-[13px] font-semibold text-white shadow-[0_3px_16px_rgba(255,122,60,0.35)] transition-all duration-200 hover:-translate-y-px hover:brightness-110 hover:shadow-[0_6px_24px_rgba(255,122,60,0.5)] active:translate-y-0 disabled:pointer-events-none disabled:opacity-40"
              disabled={!value.trim() || disabled}
              onClick={onSend}
            >
              <Send className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
              发送
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
