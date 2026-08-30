import { useEffect, useState } from "react";
import {
  ChevronRight, Eye, EyeOff, Folder, FolderOpen, Loader2, Plus, RefreshCw, X,
} from "lucide-react";
import { createWorkspaceDir, listWorkspaceDirs, type DirEntry } from "../api";
import { cn } from "../lib/utils";

/** DSH browse 目录选择对话框：浏览服务器真实目录，选中路径作为工作区。 */
export default function DirectoryPicker(props: {
  open: boolean;
  onClose: () => void;
  onSelect: (path: string) => void;
}) {
  const { open, onClose, onSelect } = props;
  const [path, setPath] = useState("");
  const [parent, setParent] = useState<string | null>(null);
  const [entries, setEntries] = useState<DirEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showHidden, setShowHidden] = useState(false);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  const join = (base: string, name: string) =>
    base ? base.replace(/[\\/]+$/, "") + "/" + name : name;

  const load = (p: string) => {
    setLoading(true);
    setError("");
    listWorkspaceDirs(p)
      .then((d) => {
        setPath(d.path);
        setParent(d.parent);
        setEntries(d.entries);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (open) load("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const enter = (name: string) => load(join(path, name));
  const up = () => parent && load(parent);

  const mkdir = async () => {
    const name = newName.trim();
    if (!name || !path) return;
    setCreating(true);
    setError("");
    try {
      await createWorkspaceDir(path, name);
      setNewName("");
      load(path);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCreating(false);
    }
  };

  if (!open) return null;

  const visible = entries.filter((e) => showHidden || !e.hidden);
  const canSelect = path !== "";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="flex h-[520px] max-h-[92vh] w-[680px] max-w-[94vw] flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* header */}
        <div className="flex items-center gap-2 border-b border-border px-4 py-3">
          <FolderOpen className="h-4 w-4 flex-none text-primary" />
          <span className="text-sm font-semibold text-foreground">选择工作区目录</span>
          <span className="ml-auto min-w-0 flex-1 truncate text-right text-[11px] text-muted-foreground" title={path}>
            {path || "（文件系统根级）"}
          </span>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* path bar */}
        <div className="flex items-center gap-1.5 border-b border-border/60 px-4 py-2">
          <button
            onClick={up}
            disabled={!parent || loading}
            className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-muted disabled:opacity-40"
            title="上一级"
          >
            <ChevronRight className="h-4 w-4 rotate-180" />
          </button>
          <div
            className="min-w-0 flex-1 truncate rounded-lg border border-border bg-background/50 px-3 py-1.5 text-xs text-foreground"
            title={path}
          >
            {path || "选择磁盘 / 目录"}
          </div>
          <button
            onClick={() => load(path)}
            disabled={loading}
            className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-muted disabled:opacity-40"
            title="刷新"
          >
            <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
          </button>
          <button
            onClick={() => setShowHidden(!showHidden)}
            className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-muted"
            title="显示隐藏项"
          >
            {showHidden ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
          </button>
        </div>

        {/* entries */}
        <div className="min-h-0 flex-1 overflow-y-auto px-2 py-2">
          {error && (
            <div className="mx-2 mb-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              {error}
            </div>
          )}
          {!loading && visible.length === 0 && (
            <div className="px-3 py-6 text-center text-xs text-muted-foreground">
              {path ? "没有子目录" : "请选择磁盘"}
            </div>
          )}
          {visible.map((e) => (
            <button
              key={e.name}
              onClick={() => enter(e.name)}
              className="flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-left text-[13px] text-foreground transition-colors hover:bg-muted"
              title={join(path, e.name)}
            >
              <Folder className="h-4 w-4 flex-none text-primary/80" />
              <span className="flex-1 truncate">{e.name}</span>
              <ChevronRight className="h-3.5 w-3.5 flex-none text-muted-foreground/50" />
            </button>
          ))}
        </div>

        {/* footer */}
        <div className="flex flex-wrap items-center gap-2 border-t border-border px-4 py-3">
          <div className="flex min-w-0 flex-1 items-center gap-1.5 rounded-lg border border-border bg-background/50 px-2.5 py-1.5">
            <Plus className="h-3.5 w-3.5 flex-none text-muted-foreground" />
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") mkdir();
              }}
              placeholder="新建文件夹名…"
              disabled={!path || creating}
              autoComplete="off"
              className="h-6 min-w-0 flex-1 bg-transparent text-xs text-foreground outline-none placeholder:text-muted-foreground"
            />
            <button
              onClick={mkdir}
              disabled={!path || !newName.trim() || creating}
              className="rounded-lg px-2 py-0.5 text-[11px] font-medium text-primary transition-colors hover:bg-primary/10 disabled:opacity-40"
            >
              {creating ? <Loader2 className="h-3 w-3 animate-spin" /> : "新建"}
            </button>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg px-3 py-1.5 text-[12px] text-muted-foreground transition-colors hover:bg-muted"
          >
            取消
          </button>
          <button
            onClick={() => canSelect && onSelect(path)}
            disabled={!canSelect}
            className="gradient-flare flex items-center gap-1.5 rounded-xl px-4 py-1.5 text-[12px] font-semibold text-white disabled:pointer-events-none disabled:opacity-40"
          >
            选择此文件夹作为工作区
          </button>
        </div>
      </div>
    </div>
  );
}
