import { useCallback, useEffect, useState } from "react";
import { Check, RefreshCw, ShieldAlert, ShieldCheck, X } from "lucide-react";
import { decideApproval, listApprovals, type ApprovalInfo } from "../api";
import { cn } from "../lib/utils";

const APPROVAL_STYLE: Record<string, { label: string; cls: string }> = {
  pending: { label: "待审批", cls: "bg-warning/15 text-warning border border-warning/30" },
  approved: { label: "已批准", cls: "bg-success/15 text-success border border-success/30" },
  rejected: { label: "已拒绝", cls: "bg-destructive/15 text-destructive border border-destructive/30" },
  timed_out: { label: "超时拒绝", cls: "bg-muted text-muted-foreground border border-border" },
};

function formatTime(ts: number): string {
  if (!ts) return "-";
  return new Date(ts * 1000).toLocaleString("zh-CN", { hour12: false });
}

function ApprovalRow({ approval, onDecided }: { approval: ApprovalInfo; onDecided: () => void }) {
  const [busy, setBusy] = useState(false);
  const st = APPROVAL_STYLE[approval.status] ?? APPROVAL_STYLE.pending;
  const decide = async (approved: boolean) => {
    if (busy) return;
    setBusy(true);
    try {
      await decideApproval(approval.approval_id, approved);
      onDecided();
    } catch {
      // 保留待审批态，可重试
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-xl border border-border bg-card/70 p-3.5">
      <div className="flex flex-wrap items-center gap-2">
        {approval.status === "pending" ? (
          <ShieldAlert className="h-4 w-4 text-warning" />
        ) : approval.status === "approved" ? (
          <ShieldCheck className="h-4 w-4 text-success" />
        ) : (
          <X className="h-4 w-4 text-muted-foreground" />
        )}
        <span className="font-mono text-[13px] text-foreground">{approval.tool_name}</span>
        <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
          {approval.permission}
        </span>
        <span className={cn("ml-auto rounded-full px-2 py-0.5 text-[10px]", st.cls)}>{st.label}</span>
      </div>
      {approval.description && (
        <p className="mt-1.5 text-[11px] text-muted-foreground">{approval.description}</p>
      )}
      <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded-lg border border-border bg-muted/40 p-2 font-mono text-[11px] leading-relaxed text-foreground">
        {JSON.stringify(approval.args, null, 2)}
      </pre>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
        <span>任务 <span className="font-mono">{approval.task_id}</span></span>
        <span>请求 {formatTime(approval.requested_at)}</span>
        {approval.status !== "pending" && (
          <span>
            决策 {formatTime(approval.decided_at ?? 0)} · {approval.decided_by || "system"}
            {approval.reason ? " · " + approval.reason : ""}
          </span>
        )}
      </div>
      {approval.status === "pending" && (
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
      )}
    </div>
  );
}

export default function ApprovalsView() {
  const [approvals, setApprovals] = useState<ApprovalInfo[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(() => {
    setBusy(true);
    listApprovals(false)
      .then((lst) => {
        setApprovals(lst);
        setError("");
      })
      .catch(() => setError("加载失败，请重试"))
      .finally(() => setBusy(false));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // 有待审批时 5s 自动刷新（审批中心是实时决策台）
  useEffect(() => {
    const hasPending = approvals.some((a) => a.status === "pending");
    if (!hasPending) return;
    const timer = window.setInterval(() => {
      listApprovals(false).then(setApprovals).catch(() => undefined);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [approvals]);

  const pendingCount = approvals.filter((a) => a.status === "pending").length;

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      <div className="mx-auto flex w-full max-w-[820px] flex-col gap-3 px-6 py-6 pb-8">
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-5 w-5 text-warning" />
          <h1 className="text-lg font-semibold">审批中心</h1>
          {pendingCount > 0 && (
            <span className="rounded-full bg-warning/15 px-2 py-0.5 text-[11px] text-warning">
              {pendingCount} 条待审批
            </span>
          )}
          <button
            className="ml-auto flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-[12px] text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50"
            onClick={refresh}
            disabled={busy}
          >
            <RefreshCw className={cn("h-3.5 w-3.5", busy && "animate-spin")} />
            刷新
          </button>
        </div>
        <p className="text-[12px] text-muted-foreground">
          敏感操作（默认破坏性工具）在执行前挂起等待人工批准；获批一次后同会话内 TOFU
          自动放行，避免审批疲劳。
        </p>
        {error && <div className="text-[12px] text-destructive">{error}</div>}
        {approvals.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border p-10 text-center text-[13px] text-muted-foreground">
            暂无审批记录。让 Agent 执行破坏性操作（如「沙箱执行」）时，这里会出现待审批请求。
          </div>
        ) : (
          approvals.map((a) => <ApprovalRow key={a.approval_id} approval={a} onDecided={refresh} />)
        )}
      </div>
    </div>
  );
}
