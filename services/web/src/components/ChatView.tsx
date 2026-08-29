import { useEffect, useRef, useState } from "react";
import { Check, ShieldAlert, ShieldCheck, X } from "lucide-react";
import { decideApproval, type ApprovalInfo } from "../api";
import { cn } from "../lib/utils";
import type { Item } from "../types";
import FlareLogo from "./FlareLogo";
import ThinkingOrb from "./ThinkingOrb";
import ToolCallCard from "./ToolCallCard";
import WelcomePanel from "./WelcomePanel";

// 打字机流式文本
function StreamText({ text, done }: { text: string; done: boolean }) {
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
      {!done && <span className="ml-0.5 inline-block h-[1em] w-[2px] animate-pulse bg-primary" />}
    </span>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] whitespace-pre-wrap break-words rounded-2xl rounded-br-sm border border-border bg-secondary px-4 py-2.5 text-[14px] leading-relaxed">
        {text}
      </div>
    </div>
  );
}

function AssistantBubble({ text, done }: { text: string; done: boolean }) {
  return (
    <div className="flex items-start gap-2.5">
      <FlareLogo size={22} animated={!done} className="mt-1" />
      <div className="whitespace-pre-wrap break-words rounded-2xl rounded-bl-sm px-1 py-0.5 text-[14px] leading-relaxed">
        <StreamText text={text} done={done} />
      </div>
    </div>
  );
}

function StatusLine({ text, tone }: { text: string; tone: "info" | "warn" | "error" }) {
  return (
    <div className={cn("text-xs", tone === "error" ? "text-destructive" : tone === "warn" ? "text-warning" : "text-muted-foreground")}>
      {text}
    </div>
  );
}

const PERMISSION_LABEL: Record<string, string> = {
  read: "只读",
  write: "写入",
  destructive: "破坏性",
};

const APPROVAL_STYLE: Record<string, { label: string; cls: string }> = {
  pending: { label: "待审批", cls: "bg-warning/15 text-warning border border-warning/30" },
  approved: { label: "已批准", cls: "bg-success/15 text-success border border-success/30" },
  rejected: { label: "已拒绝", cls: "bg-destructive/15 text-destructive border border-destructive/30" },
  timed_out: { label: "超时拒绝", cls: "bg-muted text-muted-foreground border border-border" },
};

function ApprovalCard({ approval }: { approval: ApprovalInfo }) {
  const [busy, setBusy] = useState(false);
  const st = APPROVAL_STYLE[approval.status] ?? APPROVAL_STYLE.pending;
  const decide = async (approved: boolean) => {
    if (busy) return;
    setBusy(true);
    try {
      await decideApproval(approval.approval_id, approved);
      // 状态由服务端后续 SSE approval_decision 事件回灌更新（SSE 回放是唯一数据源）
    } catch {
      // ignore：卡片保留待审批态，可重试
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl border border-warning/30 bg-warning/5 p-3">
      <div className="flex items-center gap-2">
        <ShieldAlert className="h-4 w-4 text-warning" />
        <span className="text-[13px] font-semibold">需要审批</span>
        <span className={cn("ml-auto rounded-full px-2 py-0.5 text-[10px]", st.cls)}>{st.label}</span>
      </div>
      <div className="mt-2 flex items-center gap-2 font-mono text-[13px]">
        <span className="text-foreground">{approval.tool_name}</span>
        <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">{PERMISSION_LABEL[approval.permission] ?? approval.permission}</span>
      </div>
      {approval.description && <p className="mt-1 text-[11px] text-muted-foreground">{approval.description}</p>}
      <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded-lg border border-border bg-muted/40 p-2 font-mono text-[11px] leading-relaxed text-foreground">
        {JSON.stringify(approval.args, null, 2)}
      </pre>
      {approval.status === "pending" ? (
        <div className="mt-2.5 flex gap-2">
          <button
            className="flex items-center gap-1 rounded-lg bg-success px-3 py-1.5 text-[12px] font-medium text-success-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
            disabled={busy}
            onClick={() => decide(true)}
          >
            <Check className="h-3.5 w-3.5" />
            批准执行
          </button>
          <button
            className="flex items-center gap-1 rounded-lg bg-destructive px-3 py-1.5 text-[12px] font-medium text-destructive-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
            disabled={busy}
            onClick={() => decide(false)}
          >
            <X className="h-3.5 w-3.5" />
            拒绝
          </button>
        </div>
      ) : (
        <div className="mt-2 flex items-center gap-2 text-[11px] text-muted-foreground">
          {approval.status === "approved" ? <ShieldCheck className="h-3.5 w-3.5 text-success" /> : <X className="h-3.5 w-3.5" />}
          {approval.decided_by && <span>{approval.decided_by} · </span>}
          {approval.reason || approval.status}
        </div>
      )}
    </div>
  );
}

function renderItem(it: Item) {
  switch (it.kind) {
    case "user":
      return <UserBubble key={it.id} text={it.text} />;
    case "assistant":
      return <AssistantBubble key={it.id} text={it.msg.text} done={it.msg.done} />;
    case "tool":
      return (
        <ToolCallCard key={it.id} name={it.name} args={it.args} status={it.status} result={it.result} />
      );
    case "status":
      return <StatusLine key={it.id} text={it.text} tone={it.tone} />;
    case "approval":
      return <ApprovalCard key={it.id} approval={it.approval} />;
  }
}

export default function ChatView({ items, running, onPick }: { items: Item[]; running: boolean; onPick: (text: string) => void }) {
  const endRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [items.length]);
  const hasContent = items.length > 0;
  return (
    <div className="flex-1 overflow-y-auto">
      {!hasContent ? (
        <WelcomePanel onPick={onPick} />
      ) : (
        <div className="mx-auto flex w-full max-w-[820px] flex-col gap-3 px-6 py-6 pb-8">
          {items.map((it) => renderItem(it))}
          {running && (
            <div className="flex items-center gap-2 text-[13px] text-muted-foreground">
              <ThinkingOrb active size={16} />
              <span>思考中…</span>
            </div>
          )}
          <div ref={endRef} />
        </div>
      )}
    </div>
  );
}
