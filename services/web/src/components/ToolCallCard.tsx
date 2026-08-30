import { useState } from "react";
import { CheckCircle2, ChevronDown, Loader2, XCircle } from "lucide-react";
import { cn, relTime } from "../lib/utils";
import type { ToolResult } from "../types";

// 工具调用卡：折叠态 = 紧凑药丸；展开态 = 全宽卡片（参数 + 输出）。
// 展开/收起用 grid-rows 过渡动画，运行态呼吸边框，成功对勾带 glow。
export default function ToolCallCard({
  name,
  args,
  status,
  result,
  ts,
}: {
  name: string;
  args: Record<string, unknown>;
  status: "running" | "done";
  result?: ToolResult;
  ts?: number;
}) {
  const [open, setOpen] = useState(false);
  const [showOutput, setShowOutput] = useState(false);
  const ok = result ? result.ok : true;
  const state = status === "running" ? "running" : ok ? "success" : "error";

  const statusIcon =
    state === "running" ? (
      <Loader2 className="h-3.5 w-3.5 animate-spin text-running" />
    ) : state === "success" ? (
      <CheckCircle2 className="h-3.5 w-3.5 text-success drop-shadow-[0_0_6px_rgba(52,211,153,0.5)]" />
    ) : (
      <XCircle className="h-3.5 w-3.5 text-destructive" />
    );
  const statusColor =
    state === "running"
      ? "text-running border-running/40"
      : state === "success"
        ? "text-success border-success/35"
        : "text-destructive border-destructive/35";

  const fmtInput = (v: unknown) => {
    try {
      return JSON.stringify(v, null, 2);
    } catch {
      return String(v);
    }
  };
  const inputSummary = (() => {
    try {
      const s = JSON.stringify(args);
      return s.length > 60 ? s.slice(0, 60) + "…" : s;
    } catch {
      return "";
    }
  })();
  const tag = status === "running" ? "运行中" : ok ? result?.error_code || "成功" : result?.error_code || "失败";

  return (
    <div className="mt-1.5 w-fit max-w-full">
      <button
        onClick={() => setOpen(!open)}
        title="点击查看参数/输出"
        className={cn(
          "inline-flex max-w-full items-center gap-1.5 rounded-full border bg-muted/40 px-2.5 py-1 text-[11px] backdrop-blur-sm transition-all duration-200 hover:bg-muted/70 hover:shadow-[0_2px_12px_rgba(0,0,0,0.25)]",
          statusColor,
          state === "running" && "animate-tool-running"
        )}
      >
        {statusIcon}
        <span className="truncate font-mono font-medium">{name}</span>
        {inputSummary && <span className="truncate font-mono text-muted-foreground">{inputSummary}</span>}
        <span className="flex-none text-[10px] text-muted-foreground">{tag}</span>
        <ChevronDown className={cn("h-3 w-3 flex-none opacity-60 transition-transform duration-200", open && "rotate-180")} />
      </button>

      {/* grid-rows 过渡动画（0fr -> 1fr 展开/收起） */}
      <div className={cn("grid transition-[grid-template-rows] duration-300 ease-out", open ? "grid-rows-[1fr]" : "grid-rows-[0fr]")}>
        <div className="overflow-hidden">
          <div className={cn("mt-1.5 overflow-hidden rounded-xl border bg-muted/40 text-xs backdrop-blur-sm", statusColor)}>
            <div className="border-t border-border px-3 py-2.5">
              <span className="mb-1.5 flex items-center justify-between">
                <span className="font-medium text-muted-foreground">输入参数</span>
                {ts && <span className="text-[10px] text-muted-foreground/50">{relTime(ts)}</span>}
              </span>
              <pre className="max-h-[180px] overflow-auto rounded-lg bg-background/60 p-2 font-mono text-[11px] leading-relaxed">
                {fmtInput(args)}
              </pre>
              {result && (
                <>
                  <button
                    className="mt-2.5 flex items-center gap-1 text-[11px] font-medium text-muted-foreground hover:text-foreground"
                    onClick={() => setShowOutput(!showOutput)}
                  >
                    <ChevronDown className={cn("h-3 w-3 transition-transform duration-200", showOutput && "rotate-180")} />
                    输出结果（{(result.content || "").length} 字符）
                  </button>
                  <div className={cn("grid transition-[grid-template-rows] duration-300", showOutput ? "grid-rows-[1fr]" : "grid-rows-[0fr]")}>
                    <div className="overflow-hidden">
                      <pre className={cn("mt-1.5 max-h-[240px] overflow-auto rounded-lg bg-background/60 p-2 font-mono text-[11px] leading-relaxed", !ok && "text-destructive")}>
                        {result.content || "(空)"}
                      </pre>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
