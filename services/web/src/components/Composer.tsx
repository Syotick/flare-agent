import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, Lock, Send, ShieldCheck, Sparkles, Square, Zap } from "lucide-react";
import { cn } from "../lib/utils";
import type { ModelProfile } from "../api";

// DSH 对齐：权限模式（read-only | approval | unrestricted）
export const PERMISSION_MODES = [
  { id: "read-only", label: "只读", desc: "只能读代码，不能写文件或跑命令", icon: Lock },
  { id: "approval", label: "批准", desc: "写文件 / 跑命令需逐次审批", icon: ShieldCheck },
  { id: "unrestricted", label: "无限制", desc: "全部操作自动执行，不审批", icon: Zap },
] as const;

function Dropdown({ open, setOpen, children }: { open: boolean; setOpen: (v: boolean) => void; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open, setOpen]);
  return (
    <div ref={ref} className="relative">
      {children}
    </div>
  );
}

export default function Composer(props: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  onStop: () => void;
  onKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  disabled: boolean;
  running: boolean;
  permissionMode: string;
  onPermissionMode: (v: string) => void;
  model: string | null;
  onModel: (v: string | null) => void;
  modelList: ModelProfile[];
  activeModelName: string;
}) {
  const { value, onChange, onSend, onStop, onKeyDown, disabled, running, permissionMode, onPermissionMode, model, onModel, modelList, activeModelName } = props;
  const [focused, setFocused] = useState(false);
  const [permOpen, setPermOpen] = useState(false);
  const [modelOpen, setModelOpen] = useState(false);
  const taRef = useRef<HTMLTextAreaElement | null>(null);

  const curMode = PERMISSION_MODES.find((m) => m.id === permissionMode) ?? PERMISSION_MODES[1];
  const curProfile = model ? modelList.find((p) => p.id === model) : null;
  const modelLabel = curProfile ? curProfile.name : "默认 · " + (activeModelName || "未配置");

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
        {/* DSH 对齐：会话级 模式 + 模型 选择（chip 下拉，当前值高亮） */}
        <div className="flex flex-wrap items-center gap-2">
          <Dropdown open={permOpen} setOpen={setPermOpen}>
            <button
              onClick={() => { setPermOpen(!permOpen); setModelOpen(false); }}
              className="flex items-center gap-1.5 rounded-full border border-border bg-muted/40 px-2.5 py-1 text-[11.5px] text-foreground transition-colors hover:border-primary/40 hover:bg-muted/70"
              title="权限模式"
            >
              <curMode.icon className="h-3 w-3 text-primary" />
              {curMode.label}
              <ChevronDown className={cn("h-3 w-3 text-muted-foreground transition-transform", permOpen && "rotate-180")} />
            </button>
            {permOpen && (
              <div className="absolute left-0 top-full z-40 mt-1 w-60 overflow-hidden rounded-xl border border-border bg-card p-1 shadow-2xl">
                {PERMISSION_MODES.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => { onPermissionMode(m.id); setPermOpen(false); }}
                    className={cn(
                      "flex w-full items-start gap-2 rounded-lg px-2.5 py-2 text-left transition-colors",
                      permissionMode === m.id ? "bg-primary/10" : "hover:bg-muted"
                    )}
                  >
                    <m.icon className={cn("mt-0.5 h-3.5 w-3.5 flex-none", permissionMode === m.id ? "text-primary" : "text-muted-foreground")} />
                    <span className="flex min-w-0 flex-col gap-0.5">
                      <span className={cn("text-[12.5px] font-medium", permissionMode === m.id && "text-foreground")}>{m.label}</span>
                      <span className="text-[11px] leading-snug text-muted-foreground">{m.desc}</span>
                    </span>
                    {permissionMode === m.id && <Check className="ml-auto mt-0.5 h-3.5 w-3.5 flex-none text-primary" />}
                  </button>
                ))}
              </div>
            )}
          </Dropdown>

          <Dropdown open={modelOpen} setOpen={setModelOpen}>
            <button
              onClick={() => { setModelOpen(!modelOpen); setPermOpen(false); }}
              className="flex max-w-[220px] items-center gap-1.5 rounded-full border border-border bg-muted/40 px-2.5 py-1 text-[11.5px] text-foreground transition-colors hover:border-primary/40 hover:bg-muted/70"
              title="选择模型"
            >
              <Sparkles className="h-3 w-3 flex-none text-accent" />
              <span className="truncate">{modelLabel}</span>
              <ChevronDown className={cn("h-3 w-3 flex-none text-muted-foreground transition-transform", modelOpen && "rotate-180")} />
            </button>
            {modelOpen && (
              <div className="absolute left-0 top-full z-40 mt-1 max-h-72 w-72 overflow-y-auto rounded-xl border border-border bg-card p-1 shadow-2xl">
                <button
                  onClick={() => { onModel(null); setModelOpen(false); }}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left transition-colors",
                    !model ? "bg-primary/10" : "hover:bg-muted"
                  )}
                >
                  <span className="flex min-w-0 flex-col gap-0.5">
                    <span className="text-[12.5px] font-medium">默认模型</span>
                    <span className="truncate text-[11px] text-muted-foreground">{activeModelName || "当前激活模型"}</span>
                  </span>
                  {!model && <Check className="ml-auto h-3.5 w-3.5 flex-none text-primary" />}
                </button>
                {modelList.length > 0 && <div className="mx-2 my-1 h-px bg-border" />}
                {modelList.length === 0 && (
                  <div className="px-2.5 py-2 text-[11px] text-muted-foreground">没有自定义模型，可在「模型」页添加</div>
                )}
                {modelList.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => { onModel(p.id); setModelOpen(false); }}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left transition-colors",
                      model === p.id ? "bg-primary/10" : "hover:bg-muted"
                    )}
                  >
                    <span className="flex min-w-0 flex-col gap-0.5">
                      <span className="truncate text-[12.5px] font-medium">{p.name}</span>
                      <span className="truncate text-[11px] text-muted-foreground">{p.model_name}</span>
                    </span>
                    {model === p.id && <Check className="ml-auto h-3.5 w-3.5 flex-none text-primary" />}
                  </button>
                ))}
              </div>
            )}
          </Dropdown>

          <span className="ml-auto hidden text-[11px] text-muted-foreground/70 sm:inline">{curMode.desc}</span>
        </div>

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
