import { useCallback, useEffect, useState } from "react";
import {
  Boxes, BrainCircuit, ChevronDown, ChevronRight, Cpu, Loader2, Plug, Puzzle, RefreshCw, Workflow,
} from "lucide-react";
import {
  getSkill, getSubagentStatus, listMcpServers, listSkills, listTools,
  type McpServerStatus, type SkillDetail, type SkillInfo, type SubagentStatus,
  type ToolInfo,
} from "../api";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { cn } from "../lib/utils";

type Tab = "tools" | "skills" | "mcp" | "subagent";

const TABS: { id: Tab; label: string; icon: typeof Boxes }[] = [
  { id: "tools", label: "工具", icon: Boxes },
  { id: "skills", label: "技能", icon: Puzzle },
  { id: "mcp", label: "连接", icon: Plug },
  { id: "subagent", label: "多 Agent", icon: Workflow },
];

const STATUS_STYLE: Record<string, string> = {
  completed: "bg-success/15 text-success border border-success/30",
  running: "bg-warning/15 text-warning border border-warning/30",
  pending: "bg-muted text-muted-foreground border border-border",
  failed: "bg-destructive/15 text-destructive border border-destructive/30",
  timed_out: "bg-destructive/15 text-destructive border border-destructive/30",
};

function statusBadge(status: string): string {
  return STATUS_STYLE[status] ?? "bg-muted text-muted-foreground border border-border";
}

export default function CapabilitiesView() {
  const [tab, setTab] = useState<Tab>("tools");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [skills, setSkills] = useState<SkillInfo[]>([]);
  const [mcp, setMcp] = useState<McpServerStatus[]>([]);
  const [sub, setSub] = useState<SubagentStatus | null>(null);
  const [skillDetail, setSkillDetail] = useState<SkillDetail | null>(null);
  const [openSchema, setOpenSchema] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const [t, s, m, a] = await Promise.all([
        listTools(), listSkills(), listMcpServers(), getSubagentStatus(),
      ]);
      setTools(t);
      setSkills(s);
      setMcp(m);
      setSub(a);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const openSkill = async (name: string) => {
    if (skillDetail && skillDetail.name === name) {
      setSkillDetail(null);
      return;
    }
    try {
      setSkillDetail(await getSkill(name));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const renderTab = () => {
    switch (tab) {
      case "tools":
        return (
          <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
            {tools.map((t) => (
              <Card key={t.name}>
                <CardHeader className="flex flex-row items-start justify-between gap-2">
                  <CardTitle className="font-mono text-[13px]">{t.name}</CardTitle>
                  <button
                    className="flex flex-none items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
                    onClick={() => setOpenSchema(openSchema === t.name ? null : t.name)}
                  >
                    {openSchema === t.name ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                    Schema
                  </button>
                </CardHeader>
                <CardContent className="flex flex-col gap-2">
                  <p className="text-[12px] text-muted-foreground">{t.description || "（无描述）"}</p>
                  {openSchema === t.name && (
                    <pre className="max-h-56 overflow-y-auto rounded-lg border border-border bg-muted/40 p-2 font-mono text-[10px] leading-relaxed text-foreground">
                      {JSON.stringify(t.parameters, null, 2)}
                    </pre>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        );
      case "skills":
        return (
          <div className="flex flex-col gap-3">
            {skills.length === 0 && (
              <div className="rounded-lg border border-border bg-muted/30 px-3 py-4 text-xs text-muted-foreground">
                暂无已安装技能（可先将技能包放入技能目录后刷新）。
              </div>
            )}
            {skills.map((s) => (
              <Card key={s.name}>
                <CardHeader className="cursor-pointer flex-row items-center justify-between gap-2" onClick={() => openSkill(s.name)}>
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <Puzzle className="h-4 w-4 text-primary" />
                    {s.name}
                    <span className="text-[11px] font-normal text-muted-foreground">{s.description}</span>
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    {s.required_tools.length > 0 && (
                      <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">依赖 {s.required_tools.length} 工具</span>
                    )}
                    {s.resource_count > 0 && (
                      <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">{s.resource_count} 资源</span>
                    )}
                    {skillDetail && skillDetail.name === s.name ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                  </div>
                </CardHeader>
                {skillDetail && skillDetail.name === s.name && (
                  <CardContent className="flex flex-col gap-2.5">
                    <div className="flex flex-wrap gap-1.5">
                      {skillDetail.required_tools.map((rt) => (
                        <span key={rt} className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">{rt}</span>
                      ))}
                    </div>
                    <pre className="whitespace-pre-wrap rounded-lg border border-border bg-muted/40 p-2.5 font-mono text-[11px] leading-relaxed text-foreground">
                      {skillDetail.instructions}
                    </pre>
                    {Object.keys(skillDetail.resources).length > 0 && (
                      <div className="flex flex-col gap-1.5">
                        <span className="text-[11px] font-semibold text-muted-foreground">资源</span>
                        {Object.entries(skillDetail.resources).map(([rel, content]) => (
                          <pre key={rel} className="whitespace-pre-wrap rounded-lg border border-border bg-muted/40 p-2 font-mono text-[10px] leading-relaxed text-foreground">
                            <span className="text-primary">{rel}</span>
                            {"\n"}
                            {content}
                          </pre>
                        ))}
                      </div>
                    )}
                  </CardContent>
                )}
              </Card>
            ))}
          </div>
        );
      case "mcp":
        return (
          <div className="flex flex-col gap-3">
            {mcp.length === 0 && (
              <div className="rounded-lg border border-border bg-muted/30 px-3 py-4 text-xs text-muted-foreground">
                尚未配置任何外部连接。
              </div>
            )}
            {mcp.map((s) => (
              <Card key={s.name}>
                <CardHeader className="flex flex-row items-center justify-between gap-2">
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <Plug className="h-4 w-4 text-primary" />
                    <span className="font-mono">{s.name}</span>
                    <span className="rounded-full bg-muted px-2 py-0.5 font-mono text-[10px] text-muted-foreground">{s.transport}</span>
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    <span className={cn("rounded-full px-2 py-0.5 text-[10px]", s.connected ? "bg-success/15 text-success border border-success/30" : "bg-muted text-muted-foreground border border-border")}>
                      {s.connected ? "已连接" : "未连接"}
                    </span>
                    <span className={cn("rounded-full px-2 py-0.5 text-[10px]", s.enabled ? "bg-success/15 text-success border border-success/30" : "bg-muted text-muted-foreground border border-border")}>
                      {s.enabled ? "启用" : "禁用"}
                    </span>
                  </div>
                </CardHeader>
                <CardContent className="flex flex-col gap-1.5">
                  {s.tools_registered.length === 0 ? (
                    <span className="text-[11px] text-muted-foreground">暂无注册工具</span>
                  ) : (
                    <div className="flex flex-wrap gap-1.5">
                      {s.tools_registered.map((t) => (
                        <span key={t} className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">{t}</span>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        );
      case "subagent":
        return (
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2 rounded-xl border border-border bg-muted/30 px-4 py-3 text-xs text-muted-foreground">
              <BrainCircuit className="h-4 w-4 text-primary" />
              <span>
                当前活跃子 Agent：<span className="font-mono text-foreground">{sub ? sub.active_count : "-"}</span> / 64
              </span>
              <span className="ml-auto">子任务由独立 Agent 并行执行</span>
            </div>
            {sub && sub.records.length === 0 && (
              <div className="rounded-lg border border-border bg-muted/30 px-3 py-4 text-xs text-muted-foreground">
                暂无子任务记录——在对话里让 Agent 使用 spawn_subagent / run_subagents 并行编排后即可在这里看到。
              </div>
            )}
            {sub &&
              sub.records.map((rec) => (
                <Card key={rec.subagent_id}>
                  <CardHeader className="flex flex-row items-center justify-between gap-2">
                    <CardTitle className="flex items-center gap-2 font-mono text-[13px]">
                      <Cpu className="h-4 w-4 text-primary" />
                      {rec.subagent_id}
                    </CardTitle>
                    <span className={cn("rounded-full px-2 py-0.5 text-[10px]", statusBadge(rec.status))}>{rec.status}</span>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-2">
                    <p className="text-[12px] text-muted-foreground">{rec.prompt}</p>
                    <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
                      <span>步骤 {rec.step_count}</span>
                      {rec.error && <span className="text-destructive">{rec.error}</span>}
                    </div>
                    {rec.output && (
                      <pre className="whitespace-pre-wrap rounded-lg border border-border bg-muted/40 p-2.5 font-mono text-[11px] leading-relaxed text-foreground">{rec.output}</pre>
                    )}
                  </CardContent>
                </Card>
              ))}
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="flex min-w-0 flex-1 flex-col gap-4 overflow-y-auto p-5">
      <div className="flex items-center gap-2">
        <Boxes className="h-5 w-5 text-primary" />
        <h1 className="text-lg font-semibold tracking-tight">能力中心</h1>
        <span className="text-xs text-muted-foreground">工具 · 技能 · 外部连接 · 并行任务</span>
        <div className="ml-auto">
          <Button variant="outline" size="sm" onClick={refresh} disabled={busy}>
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            刷新
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">{error}</div>
      )}

      {/* 页签 */}
      <div className="flex gap-1.5 border-b border-border pb-1.5">
        {TABS.map((tb) => {
          const Icon = tb.icon;
          const active = tab === tb.id;
          return (
            <button
              key={tb.id}
              onClick={() => setTab(tb.id)}
              className={cn(
                "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] transition-colors",
                active ? "bg-gradient-flare-soft text-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              <Icon className={cn("h-3.5 w-3.5", active && "text-primary")} />
              {tb.label}
            </button>
          );
        })}
      </div>

      {renderTab()}
    </div>
  );
}
