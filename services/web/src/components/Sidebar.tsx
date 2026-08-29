import { useState } from "react";
import {
  Activity, Brain, Cpu, Database, MessageSquare, Plus, Puzzle, Search, ShieldCheck, Terminal, Trash2, X,
} from "lucide-react";
import { cn, groupByDate, autoTitle } from "../lib/utils";
import type { TaskDetail } from "../api";
import FlareLogo from "./FlareLogo";
import type { ViewId } from "../App";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "./ui/alert-dialog";

export default function Sidebar(props: {
  tasks: TaskDetail[];
  activeTaskId: string | null;
  onPick: (taskId: string) => void;
  onNew: () => void;
  onDelete: (taskId: string) => void;
  running: boolean;
  view: ViewId;
  onNavigate: (view: ViewId) => void;
  pendingApprovals: number;
}) {
  const { tasks, activeTaskId, onPick, onNew, onDelete, running, view, onNavigate, pendingApprovals } = props;
  const [query, setQuery] = useState("");
  const [confirm, setConfirm] = useState<TaskDetail | null>(null);

  const q = query.trim().toLowerCase();
  const filtered = q
    ? tasks.filter((t) => (t.task_input || "").toLowerCase().indexOf(q) >= 0)
    : tasks;
  const groups = groupByDate(filtered);

  const statusColor = (s: string) =>
    s === "completed" ? "bg-success"
    : s === "failed" ? "bg-destructive"
    : s === "budget_exceeded" || s === "awaiting_approval" ? "bg-warning"
    : "bg-muted-foreground";

  return (
    <aside
      className="relative flex h-full w-[264px] flex-none flex-col gap-4 overflow-hidden border-r border-border/80 px-3 py-4 backdrop-blur-xl"
      style={{ background: "linear-gradient(180deg, hsl(28 100% 55% / 0.1), hsl(18 18% 5%) 34%), hsl(18 16% 8%)" }}
    >
      {/* Brand */}
      <div className="flex items-center gap-2.5 px-2">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-card/60 shadow-[0_4px_16px_rgba(255,122,60,0.2)] ring-1 ring-primary/20">
          <FlareLogo size={30} animated />
        </div>
        <div className="h-px w-full bg-gradient-to-r from-transparent via-primary/30 to-transparent" />
        <div className="flex flex-col leading-tight">
          <span className="text-gradient text-[15px] font-bold">Flare</span>
          <span className="text-[11px] text-muted-foreground">AI Agent Console</span>
        </div>
      </div>

      {/* 会话 */}
      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto">
        <div className="flex items-center justify-between px-2">
          <span className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">会话</span>
          <button className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-primary" title="新建会话" onClick={onNew}>
            <Plus className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* 搜索框 */}
        <div className="mx-0.5 flex items-center gap-1.5 rounded-lg border border-border bg-input px-2.5 focus-within:border-primary/45 focus-within:ring-2 focus-within:ring-primary/10">
          <Search className="h-3 w-3 flex-none text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜索会话…"
            autoComplete="off"
            className="h-8 min-w-0 flex-1 bg-transparent text-xs text-foreground outline-none placeholder:text-muted-foreground"
          />
          {query && (
            <button className="text-muted-foreground hover:text-foreground" onClick={() => setQuery("")} title="清除">
              <X className="h-3 w-3" />
            </button>
          )}
        </div>

        {filtered.length === 0 && (
          <div className="px-2.5 py-2 text-xs text-muted-foreground">
            {tasks.length === 0 ? "还没有会话，点 ＋ 新建" : "没有匹配的会话"}
          </div>
        )}
        {groups.map((g) => (
          <div key={g.label} className="flex flex-col gap-0.5">
            <span className="px-2 pt-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">{g.label}</span>
            {g.items.map((t) => (
              <div
                key={t.task_id}
                className={cn(
                  "group flex cursor-pointer items-center gap-2 rounded-lg border border-transparent px-2.5 py-2 text-[13px] text-muted-foreground transition-all hover:translate-x-0.5 hover:bg-muted hover:text-foreground",
                  t.task_id === activeTaskId && "gradient-flare-soft border-primary/20 text-foreground"
                )}
                onClick={() => onPick(t.task_id)}
              >
                <MessageSquare className="h-3 w-3 flex-none opacity-70" />
                <span className="flex-1 truncate">{autoTitle(t.task_input)}</span>
                <span className="hidden items-center gap-1 group-hover:flex">
                  <span className={cn("h-1.5 w-1.5 rounded-full", statusColor(t.status), t.status === "running" && "animate-pulse")} />
                  <button
                    className="rounded-md p-1 text-muted-foreground hover:bg-destructive/15 hover:text-destructive"
                    title="删除会话"
                    onClick={(e) => { e.stopPropagation(); setConfirm(t); }}
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </span>
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* 导航 */}
      <div className="flex flex-none flex-col gap-1.5">
        <div className="flex flex-col gap-0.5">
          <span className="px-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">工作区</span>
          <div
            className={
              "flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13px] transition-colors " +
              (view === "chat"
                ? "bg-gradient-flare-soft text-foreground"
                : "text-muted-foreground/60 hover:bg-muted hover:text-foreground")
            }
            onClick={() => onNavigate("chat")}
          >
            <MessageSquare className={"h-3.5 w-3.5 " + (view === "chat" ? "text-primary" : "")} />
            <span className={view === "chat" ? "font-medium" : ""}>对话</span>
          </div>
          <div
            className={
              "flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13px] transition-colors " +
              (view === "kb"
                ? "bg-gradient-flare-soft text-foreground"
                : "text-muted-foreground/60 hover:bg-muted hover:text-foreground")
            }
            onClick={() => onNavigate("kb")}
          >
            <Database className={"h-3.5 w-3.5 " + (view === "kb" ? "text-primary" : "")} />
            <span className={view === "kb" ? "font-medium" : ""}>知识库</span>
            <span className="ml-auto rounded-full bg-muted px-1.5 py-0.5 text-[9px]">M3a</span>
          </div>
          <div
            className={
              "flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13px] transition-colors " +
              (view === "memory"
                ? "bg-gradient-flare-soft text-foreground"
                : "text-muted-foreground/60 hover:bg-muted hover:text-foreground")
            }
            onClick={() => onNavigate("memory")}
          >
            <Brain className={"h-3.5 w-3.5 " + (view === "memory" ? "text-primary" : "")} />
            <span className={view === "memory" ? "font-medium" : ""}>记忆</span>
            <span className="ml-auto rounded-full bg-muted px-1.5 py-0.5 text-[9px]">M3b</span>
          </div>
          <div
            className={
              "flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13px] transition-colors " +
              (view === "ops"
                ? "bg-gradient-flare-soft text-foreground"
                : "text-muted-foreground/60 hover:bg-muted hover:text-foreground")
            }
            onClick={() => onNavigate("ops")}
          >
            <Activity className={"h-3.5 w-3.5 " + (view === "ops" ? "text-primary" : "")} />
            <span className={view === "ops" ? "font-medium" : ""}>运维</span>
            <span className="ml-auto rounded-full bg-muted px-1.5 py-0.5 text-[9px]">M6</span>
          </div>
          <div
            className={
              "flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13px] transition-colors " +
              (view === "approvals"
                ? "bg-gradient-flare-soft text-foreground"
                : "text-muted-foreground/60 hover:bg-muted hover:text-foreground")
            }
            onClick={() => onNavigate("approvals")}
          >
            <ShieldCheck className={"h-3.5 w-3.5 " + (view === "approvals" ? "text-primary" : "")} />
            <span className={view === "approvals" ? "font-medium" : ""}>审批</span>
            {pendingApprovals > 0 ? (
              <span className="ml-auto animate-pulse rounded-full bg-warning/20 px-1.5 py-0.5 text-[9px] text-warning">
                {pendingApprovals} 待批
              </span>
            ) : (
              <span className="ml-auto rounded-full bg-muted px-1.5 py-0.5 text-[9px]">F1.3</span>
            )}
          </div>
          <div
            className={
              "flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13px] transition-colors " +
              (view === "capabilities"
                ? "bg-gradient-flare-soft text-foreground"
                : "text-muted-foreground/60 hover:bg-muted hover:text-foreground")
            }
            onClick={() => onNavigate("capabilities")}
          >
            <Puzzle className={"h-3.5 w-3.5 " + (view === "capabilities" ? "text-primary" : "")} />
            <span className={view === "capabilities" ? "font-medium" : ""}>能力</span>
            <span className="ml-auto rounded-full bg-muted px-1.5 py-0.5 text-[9px]">工具·技能·MCP</span>
          </div>
          <div
            className={
              "flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13px] transition-colors " +
              (view === "model"
                ? "bg-gradient-flare-soft text-foreground"
                : "text-muted-foreground/60 hover:bg-muted hover:text-foreground")
            }
            onClick={() => onNavigate("model")}
          >
            <Cpu className={"h-3.5 w-3.5 " + (view === "model" ? "text-primary" : "")} />
            <span className={view === "model" ? "font-medium" : ""}>模型</span>
            <span className="ml-auto rounded-full bg-muted px-1.5 py-0.5 text-[9px]">网关配置</span>
          </div>
          <div
            className={
              "flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13px] transition-colors " +
              (view === "api"
                ? "bg-gradient-flare-soft text-foreground"
                : "text-muted-foreground/60 hover:bg-muted hover:text-foreground")
            }
            onClick={() => onNavigate("api")}
          >
            <Terminal className={"h-3.5 w-3.5 " + (view === "api" ? "text-primary" : "")} />
            <span className={view === "api" ? "font-medium" : ""}>开发者</span>
            <span className="ml-auto rounded-full bg-muted px-1.5 py-0.5 text-[9px]">F9.3</span>
          </div>
        </div>
      </div>

      {/* Footer：状态 */}
      <div className="flex flex-none items-center gap-2 border-t border-border px-2 pt-2.5 text-xs text-muted-foreground">
        <span className={cn("h-1.5 w-1.5 flex-none rounded-full", running ? "bg-warning shadow-[0_0_8px_rgba(242,183,78,0.7)]" : "bg-success shadow-[0_0_8px_rgba(52,211,153,0.6)]")} />
        <span className="flex-1">{running ? "运行中" : "就绪"}</span>
        <span className="font-mono text-[10px]">v0.1</span>
      </div>

      {/* 底部品牌光晕 */}
      <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-28 bg-[radial-gradient(60%_100%_at_50%_100%,rgba(255,122,60,0.12),transparent)]" />

      {/* 删除确认 */}
      <AlertDialog open={!!confirm} onOpenChange={(open) => { if (!open) setConfirm(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除会话</AlertDialogTitle>
            <AlertDialogDescription>
              确定删除会话「{confirm ? autoTitle(confirm.task_input) : ""}」？此操作不可恢复。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={() => { if (confirm) onDelete(confirm.task_id); setConfirm(null); }}>
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </aside>
  );
}
