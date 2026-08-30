import { useState } from "react";
import {
  Activity, Brain, ChevronDown, Cpu, Database, FolderOpen, MessageSquare, MoreHorizontal, Pencil, Plus, Puzzle, Search, ShieldCheck, Terminal, Trash2, X,
} from "lucide-react";
import { cn, groupByDate, autoTitle, workspaceLabel } from "../lib/utils";
import type { TaskDetail, Workspace } from "../api";
import DirectoryPicker from "./DirectoryPicker";
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
  onRename: (taskId: string, title: string) => void;
  onDeleteWorkspace: (ws: string) => void;
  running: boolean;
  view: ViewId;
  onNavigate: (view: ViewId) => void;
  pendingApprovals: number;
  buildTag?: string;
  workspaces: Workspace[];
  currentWorkspace: string | null;
  onSwitchWorkspace: (ws: string) => void;
}) {
  const { tasks, activeTaskId, onPick, onNew, onDelete, onRename, onDeleteWorkspace, running, view, onNavigate, pendingApprovals, buildTag, workspaces, currentWorkspace, onSwitchWorkspace } = props;
  const [query, setQuery] = useState("");
  const [confirm, setConfirm] = useState<TaskDetail | null>(null);
  const [rename, setRename] = useState<TaskDetail | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [wsConfirm, setWsConfirm] = useState<Workspace | null>(null);
  const [wsOpen, setWsOpen] = useState(false);
  // 会话行操作菜单（DSH 对齐：hover 出菜单按钮 → 重命名/删除）
  const [menuFor, setMenuFor] = useState<string | null>(null);
  // DSH 对齐：添加/选择工作区 = 打开应用内目录浏览器（无"输入名字"，与 DSH 一致）
  const [pickerOpen, setPickerOpen] = useState(false);

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

  // DSH 对齐：无默认工作区 —— 工作区列表不展示 "default"，只列真实创建的工作区；
  // 当前工作区若尚未持久化（首个会话前），也合成进列表以便高亮展示
  let wsList = workspaces.filter((w) => w.workspace_id !== "default");
  if (currentWorkspace && !wsList.some((w) => w.workspace_id === currentWorkspace)) {
    wsList = [...wsList, { workspace_id: currentWorkspace, task_count: 0, last_used_at: 0 }];
  }

  // DSH 对齐：没有任何工作区时，点击工作区按钮直接打开目录选择（跳过空菜单）；
  // 有工作区则展开下拉（列表 + 添加工作区）。
  const openWsMenu = () => {
    const hasWs = workspaces.some((w) => w.workspace_id !== "default") || !!currentWorkspace;
    if (!hasWs) {
      setPickerOpen(true);
      return;
    }
    setWsOpen(!wsOpen);
  };

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

      {/* DSH 对齐：工作区选择器（先选工作区，会话按工作区区分） */}
      <div className="relative flex-none px-0.5">
        <button
          onClick={openWsMenu}
          className="flex w-full items-center gap-2 rounded-lg border border-border bg-card/50 px-2.5 py-2 text-left transition-colors hover:border-primary/40"
          title="选择或添加工作区"
        >
          <FolderOpen className="h-3.5 w-3.5 flex-none text-primary" />
          <span
            className="min-w-0 flex-1 truncate text-[13px] font-medium text-foreground"
            title={currentWorkspace ?? "选择工作区"}
          >
            {currentWorkspace ? workspaceLabel(currentWorkspace) : "选择工作区"}
          </span>
          <ChevronDown className={"h-3.5 w-3.5 flex-none text-muted-foreground transition-transform " + (wsOpen ? "rotate-180" : "")} />
        </button>
        {wsOpen && (
          <div className="absolute left-0 right-0 top-full z-30 mt-1 overflow-hidden rounded-xl border border-border bg-card shadow-2xl backdrop-blur-xl">
            <div className="max-h-56 overflow-y-auto p-1">
              <div className="px-2.5 pb-1 pt-1.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
                工作区
              </div>
              {wsList.length === 0 && (
                <div className="px-2.5 py-1.5 text-xs text-muted-foreground">还没有工作区，打开文件夹新建</div>
              )}
              {wsList.map((w) => (
                <div
                  key={w.workspace_id}
                  onClick={() => { onSwitchWorkspace(w.workspace_id); setWsOpen(false); }}
                  className={
                    "group flex w-full cursor-pointer items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-[12.5px] transition-colors " +
                    (w.workspace_id === currentWorkspace
                      ? "bg-primary/10 text-foreground"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground")
                  }
                >
                  <span className="flex-1 truncate" title={w.workspace_id}>{workspaceLabel(w.workspace_id)}</span>
                  <span className="flex-none text-[10px] text-muted-foreground/60">{w.task_count}</span>
                  <button
                    className="flex-none rounded-md p-0.5 text-muted-foreground/70 opacity-0 transition-opacity hover:bg-destructive/15 hover:text-destructive group-hover:opacity-100"
                    title="删除工作区（清空其会话，不删目录）"
                    onClick={(e) => { e.stopPropagation(); setWsConfirm(w); setWsOpen(false); }}
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              ))}
            </div>
            <div className="border-t border-border p-1.5">
              <button
                className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-[12px] font-medium text-primary transition-colors hover:bg-primary/10"
                title="打开文件系统浏览并选择目录作为工作区"
                onClick={() => { setPickerOpen(true); setWsOpen(false); }}
              >
                <Plus className="h-3.5 w-3.5 flex-none" />
                添加工作区…
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 会话（先选工作区：未选时不展示会话，引导先选/建工作区） */}
      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto">
        <div className="flex items-center justify-between px-2">
          <span className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">会话</span>
          {currentWorkspace ? (
            <button className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-primary" title="新建会话" onClick={onNew}>
              <Plus className="h-3.5 w-3.5" />
            </button>
          ) : (
            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] text-primary">未选择</span>
          )}
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

        {!currentWorkspace ? (
          <div className="mx-0.5 mt-1 rounded-xl border border-dashed border-border/70 px-3 py-4 text-center text-xs leading-relaxed text-muted-foreground">
            请先选择或创建工作区，
            <br />
            再开始对话
          </div>
        ) : filtered.length === 0 && (
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
                  "group relative flex cursor-pointer items-center gap-2 rounded-lg border border-transparent px-2.5 py-2 text-[13px] text-muted-foreground transition-all hover:translate-x-0.5 hover:bg-muted hover:text-foreground",
                  t.task_id === activeTaskId && "gradient-flare-soft border-primary/20 text-foreground"
                )}
                onClick={() => onPick(t.task_id)}
              >
                <MessageSquare className="h-3 w-3 flex-none opacity-70" />
                <span className="flex-1 truncate">{t.title || autoTitle(t.task_input)}</span>
                <span className="hidden items-center gap-1 group-hover:flex">
                  <span className={cn("h-1.5 w-1.5 rounded-full", statusColor(t.status), t.status === "running" && "animate-pulse")} />
                  <button
                    className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                    title="会话操作"
                    onClick={(e) => { e.stopPropagation(); setMenuFor(menuFor === t.task_id ? null : t.task_id); }}
                  >
                    <MoreHorizontal className="h-3 w-3" />
                  </button>
                </span>
                {menuFor === t.task_id && (
                  <div className="absolute right-2 top-8 z-40 flex w-32 flex-col gap-0.5 rounded-lg border border-border bg-card p-1 shadow-2xl" onClick={(e) => e.stopPropagation()}>
                    <button
                      className="flex items-center gap-2 rounded-md px-2 py-1.5 text-left text-[11.5px] text-foreground hover:bg-muted"
                      onClick={() => { setRename(t); setRenameValue(t.title || autoTitle(t.task_input)); setMenuFor(null); }}
                    >
                      <Pencil className="h-3 w-3 text-muted-foreground" />
                      重命名
                    </button>
                    <button
                      className="flex items-center gap-2 rounded-md px-2 py-1.5 text-left text-[11.5px] text-destructive hover:bg-destructive/10"
                      onClick={() => { setConfirm(t); setMenuFor(null); }}
                    >
                      <Trash2 className="h-3 w-3" />
                      删除
                    </button>
                  </div>
                )}
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
            {pendingApprovals > 0 && (
              <span className="ml-auto animate-pulse rounded-full bg-warning/20 px-1.5 py-0.5 text-[9px] text-warning">
                {pendingApprovals} 待批
              </span>
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
            
          </div>
        </div>
      </div>

      {/* Footer：状态 */}
      <div className="flex flex-none items-center gap-2 border-t border-border px-2 pt-2.5 text-xs text-muted-foreground">
        <span className={cn("h-1.5 w-1.5 flex-none rounded-full", running ? "bg-warning shadow-[0_0_8px_rgba(242,183,78,0.7)]" : "bg-success shadow-[0_0_8px_rgba(52,211,153,0.6)]")} />
        <span className="flex-1">{running ? "运行中" : "就绪"}</span>
        {buildTag && <span className="hidden text-[10px] text-muted-foreground/60 lg:inline" title="构建时间">{buildTag}</span>}

      </div>

      {/* 底部品牌光晕 */}
      <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-28 bg-[radial-gradient(60%_100%_at_50%_100%,rgba(255,122,60,0.12),transparent)]" />

      {/* 删除确认 */}
      <AlertDialog open={!!confirm} onOpenChange={(open) => { if (!open) setConfirm(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除会话</AlertDialogTitle>
            <AlertDialogDescription>
              确定删除会话「{confirm ? (confirm.title || autoTitle(confirm.task_input)) : ""}」？此操作不可恢复。
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

      {/* 会话重命名（DSH 对齐） */}
      <AlertDialog open={!!rename} onOpenChange={(open) => { if (!open) setRename(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>重命名会话</AlertDialogTitle>
            <AlertDialogDescription>
              给会话起个新名字（只改显示名，不影响原始输入）。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <input
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && renameValue.trim()) {
                if (rename) onRename(rename.task_id, renameValue.trim());
                setRename(null);
              }
            }}
            autoFocus
            placeholder="会话标题"
            className="w-full rounded-lg border border-border bg-input px-3 py-2 text-sm text-foreground outline-none focus:border-primary/50"
          />
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={() => { if (rename && renameValue.trim()) onRename(rename.task_id, renameValue.trim()); setRename(null); }}>
              保存
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* 工作区删除（DSH 对齐：清空其会话，不删磁盘目录） */}
      <AlertDialog open={!!wsConfirm} onOpenChange={(open) => { if (!open) setWsConfirm(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>删除工作区</AlertDialogTitle>
            <AlertDialogDescription>
              确定删除工作区「{wsConfirm ? workspaceLabel(wsConfirm.workspace_id) : ""}」下的全部 {wsConfirm?.task_count ?? 0} 个会话？
              仅清空该工作区的会话，磁盘目录不会被删除。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={() => { if (wsConfirm) onDeleteWorkspace(wsConfirm.workspace_id); setWsConfirm(null); }}>
              删除工作区
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* DSH browse：工作区目录选择对话框 */}
      <DirectoryPicker
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelect={(p) => {
          onSwitchWorkspace(p);
          setPickerOpen(false);
        }}
      />
    </aside>
  );
}
