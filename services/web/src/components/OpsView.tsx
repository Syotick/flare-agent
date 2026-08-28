import { useEffect, useState } from "react";
import {
  Activity, CheckCircle2, ChevronDown, ChevronRight,
  CircleAlert, Gauge, Loader2, RefreshCw, Timer, TrendingUp,
} from "lucide-react";
import { getMetricsText, getSloStatus, type AlertSeverity, type SloStatus } from "../api";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

const SEVERITY_STYLE: Record<AlertSeverity, { label: string; cls: string; badge: string }> = {
  none: { label: "正常", cls: "text-success border-success/30 bg-success/10", badge: "bg-success/15 text-success border border-success/30" },
  warning: { label: "预警 P2", cls: "text-warning border-warning/30 bg-warning/10", badge: "bg-warning/15 text-warning border border-warning/30" },
  critical: { label: "严重 P0", cls: "text-destructive border-destructive/30 bg-destructive/10", badge: "bg-destructive/15 text-destructive border border-destructive/30" },
};

function severityLabel(s: AlertSeverity): string {
  return SEVERITY_STYLE[s].label;
}

function fmtTime(ts: number): string {
  const d = new Date(ts * 1000);
  const p = (n: number) => String(n).padStart(2, "0");
  return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) + " " + p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds());
}

export default function OpsView() {
  const [slo, setSlo] = useState<SloStatus | null>(null);
  const [metricsText, setMetricsText] = useState("");
  const [showMetrics, setShowMetrics] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = async () => {
    setBusy(true);
    setError("");
    try {
      const [s, m] = await Promise.all([getSloStatus(), getMetricsText()]);
      setSlo(s);
      setMetricsText(m);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 15000); // 15s 自动刷新
    return () => clearInterval(timer);
  }, []);

  const overall = slo ? SEVERITY_STYLE[slo.overall] : null;

  return (
    <div className="flex min-w-0 flex-1 flex-col gap-4 overflow-y-auto p-5">
      <div className="flex items-center gap-2">
        <Activity className="h-5 w-5 text-primary" />
        <h1 className="text-lg font-semibold tracking-tight">运维中心</h1>
        <span className="text-xs text-muted-foreground">SLO · 错误预算 · 告警分级（M6）</span>
        <div className="ml-auto flex items-center gap-2">
          {slo && <span className="text-[11px] text-muted-foreground">更新于 {fmtTime(slo.generated_at)}</span>}
          <Button variant="outline" size="sm" onClick={refresh} disabled={busy}>
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            刷新
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {error}
        </div>
      )}

      {slo && overall && (
        <div className={"flex items-center gap-3 rounded-xl border px-4 py-3 " + overall.cls}>
          {slo.overall === "none" ? (
            <CheckCircle2 className="h-5 w-5" />
          ) : (
            <CircleAlert className="h-5 w-5" />
          )}
          <div className="flex flex-col">
            <span className="text-sm font-semibold">整体状态：{overall.label}</span>
            <span className="text-[11px] opacity-80">
              错误预算周期 {slo.period_days} 天 · 三个 SLO 实时分级
            </span>
          </div>
        </div>
      )}


      <div className="grid min-h-0 grid-cols-1 gap-4 xl:grid-cols-3">
        {slo &&
          slo.slos.map((s) => {
            const st = SEVERITY_STYLE[s.alert.severity];
            const budget = s.budget;
            const consumedPct = budget ? Math.min(budget.consumed_ratio * 100, 100) : 0;
            return (
              <Card key={s.name}>
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle className="flex items-center gap-2 text-sm">
                    {s.name === "latency" ? (
                      <Timer className="h-4 w-4 text-primary" />
                    ) : (
                      <TrendingUp className="h-4 w-4 text-primary" />
                    )}
                    {s.name}
                  </CardTitle>
                  <span className={"rounded-full px-2 py-0.5 text-[10px] font-medium " + st.badge}>
                    {severityLabel(s.alert.severity)}
                  </span>
                </CardHeader>
                <CardContent className="flex flex-col gap-2.5">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-muted-foreground">目标</span>
                    <span className="font-mono text-foreground">
                      {s.name === "latency" ? "p95 ≤ " + s.target + "s" : "≥ " + s.target * 100 + "%"}
                    </span>
                  </div>

                  {budget ? (
                    <>
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="text-muted-foreground">错误预算</span>
                        <span className="font-mono text-foreground">
                          已用 {(budget.consumed_ratio * 100).toFixed(2)}%
                        </span>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                        <div
                          className={
                            "h-full rounded-full transition-all " +
                            (budget.consumed_ratio >= 1
                              ? "bg-destructive"
                              : budget.consumed_ratio >= 0.5
                                ? "bg-warning"
                                : "bg-success")
                          }
                          style={{ width: consumedPct + "%" }}
                        />
                      </div>
                      <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                        <span>bad {budget.bad} / {budget.total}</span>
                        <span>剩余 {(budget.remaining_ratio * 100).toFixed(1)}%</span>
                      </div>
                    </>
                  ) : (
                    <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                      <Gauge className="h-3.5 w-3.5" />
                      当前 p95 = {s.p95 != null ? s.p95.toFixed(3) + "s" : "暂无观测"}
                    </div>
                  )}

                  <div className={"rounded-lg border px-2.5 py-1.5 text-[11px] " + st.cls}>
                    {s.alert.message}
                  </div>
                </CardContent>
              </Card>
            );
          })}
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Activity className="h-4 w-4 text-primary" />
            Prometheus 指标（/metrics）
          </CardTitle>
          <button
            className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
            onClick={() => setShowMetrics((v) => !v)}
          >
            {showMetrics ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            {showMetrics ? "收起" : "展开原始指标"}
          </button>
        </CardHeader>
        {showMetrics && (
          <CardContent>
            <pre className="max-h-80 overflow-y-auto whitespace-pre-wrap rounded-lg border border-border bg-muted/40 p-2.5 font-mono text-[11px] leading-relaxed text-foreground">
              {metricsText || "暂无指标"}
            </pre>
          </CardContent>
        )}
      </Card>
    </div>
  );
}

