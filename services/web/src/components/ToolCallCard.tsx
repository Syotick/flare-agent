import { useState } from "react";
import { CheckCircle2, ChevronDown, Loader2, XCircle } from "lucide-react";
import { cn } from "../lib/utils";
import type { ToolResult } from "../types";

// 工具调用卡：折叠态 = 紧凑药丸；展开态 = 全宽卡片（参数 + 输出）
export default function ToolCallCard({
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
  const [showOutput, setShowOutput] = useState(false);
  const ok = result ? result.ok : true;
  const state = status === "running" ? "running" : ok ? "success" : "error";

  const statusIcon =
    state === "running" ? <Loader2 className="h-3.5 w-3.5 animate-spin text-running" /> :
    state === "success" ? <CheckCircle2 className="h-3.5 w-3.5 text-success" /> :
    <XCircle className="h-3.5 w-3.5 text-destructive" />;
  const statusColor =
    state === "running" ? "text-running border-running/30" :
    state === "success" ? "text-success border-success/30" :
    "text-destructive border-destructive/30";

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

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        title="点击查看参数/输出"
        className={cn(
          "mt-1.5 inline-flex max-w-full items-center gap-1.5 rounded-full border bg-muted/50 px-2.5 py-1 text-[11px] transition-colors hover:bg-muted",
          statusColor
        )}
      >
        {statusIcon}
        <span className="truncate font-mono font-medium">{name}</span>
        {inputSummary && <span className="truncate font-mono text-muted-foreground">{inputSummary}</span>}
        <span className="flex-none text-[10px] text-muted-foreground">{tag}</span>
        <ChevronDown className="h-3 w-3 flex-none opacity-60" />
      </button>
    );
  }

  return (
    <div className={cn("mt-2 overflow-hidden rounded-xl border bg-muted/50 text-xs", statusColor)}>
      <button className="flex w-full items-center gap-2 px-3 py-2 text-left" onClick={() => setOpen(false)}>
        {statusIcon}
        <span className="font-mono font-medium">{name}</span>
        <span className="flex-1 truncate font-mono text-muted-foreground">{inputSummary}</span>
        <span className="flex-none text-[10px] text-muted-foreground">{tag}</span>
        <ChevronDown className="h-3.5 w-3.5 flex-none rotate-180" />
      </button>
      <div className="border-t border-border px-3 py-2.5">
        <span className="mb-1.5 block font-medium text-muted-foreground">输入参数</span>
        <pre className="max-h-[180px] overflow-auto rounded-lg bg-background/60 p-2 font-mono text-[11px] leading-relaxed">
          {fmtInput(args)}
        </pre>
        {result && (
          <>
            <button
              className="mt-2.5 flex items-center gap-1 text-[11px] font-medium text-muted-foreground hover:text-foreground"
              onClick={() => setShowOutput(!showOutput)}
            >
              <ChevronDown className={cn("h-3 w-3 transition-transform", showOutput && "rotate-180")} />
              输出结果（{(result.content || "").length} 字符）
            </button>
            {showOutput && (
              <pre className={cn("mt-1.5 max-h-[240px] overflow-auto rounded-lg bg-background/60 p-2 font-mono text-[11px] leading-relaxed", !ok && "text-destructive")}>
                {result.content || "(空)"}
              </pre>
            )}
          </>
        )}
      </div>
    </div>
  );
}
