import { useEffect, useState } from "react";
import { Brain, Loader2, Plus, RefreshCw, Search, Trash2 } from "lucide-react";
import {
  deleteFact,
  getMemoryContext,
  listFacts,
  putFact,
  searchMemory,
  type Fact,
  type MemoryHit,
} from "../api";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Input, Textarea } from "./ui/input";
import { relTime } from "../lib/utils";

export default function MemoryView() {
  const [facts, setFacts] = useState<Fact[]>([]);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  // 新增/编辑事实
  const [key, setKey] = useState("");
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);
  // 向量记忆检索
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<MemoryHit[]>([]);
  const [searched, setSearched] = useState(false);
  // 上下文块
  const [ctxQ, setCtxQ] = useState("");
  const [budget, setBudget] = useState(1200);
  const [block, setBlock] = useState("");
  const [ctxBusy, setCtxBusy] = useState(false);

  const refresh = () => {
    listFacts()
      .then(setFacts)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  };
  useEffect(() => {
    refresh();
  }, []);

  const saveFact = async () => {
    const k = key.trim();
    const v = value.trim();
    if (!k || !v || saving) return;
    setSaving(true);
    setError("");
    setOk("");
    try {
      await putFact(k, v);
      setOk("已保存事实 " + k);
      setKey("");
      setValue("");
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const removeFact = async (k: string) => {
    setError("");
    setOk("");
    try {
      await deleteFact(k);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const editFact = (f: Fact) => {
    setKey(f.key);
    setValue(f.value);
    setOk("");
  };

  const doSearch = async () => {
    if (!q.trim()) return;
    setError("");
    try {
      setHits(await searchMemory(q.trim(), 6));
      setSearched(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const doContext = async () => {
    setCtxBusy(true);
    setError("");
    try {
      setBlock(await getMemoryContext(ctxQ.trim(), budget));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCtxBusy(false);
    }
  };

  return (

    <div className="flex min-w-0 flex-1 flex-col gap-4 overflow-y-auto p-5">
      <div className="flex items-center gap-2">
        <Brain className="h-5 w-5 text-primary" />
        <h1 className="text-lg font-semibold tracking-tight">记忆管理</h1>
        <span className="text-xs text-muted-foreground">分层记忆 · 长期事实 / 向量记忆 / 上下文工程</span>
        <div className="ml-auto">
          <Button variant="outline" size="sm" onClick={refresh} title="刷新">
            <RefreshCw className="h-3.5 w-3.5" />
            刷新
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {error}
        </div>
      )}
      {ok && (
        <div className="rounded-lg border border-success/30 bg-success/10 px-3 py-2 text-xs text-success">
          {ok}
        </div>
      )}

      <div className="grid min-h-0 grid-cols-1 gap-4 xl:grid-cols-2">
        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <Plus className="h-4 w-4 text-primary" />
                新增 / 编辑事实
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2.5">
              <Input
                placeholder="key（如：user_name）"
                value={key}
                onChange={(e) => setKey(e.target.value)}
              />
              <Textarea
                placeholder="value（事实内容，如：用户叫小明）"
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
              <Button onClick={saveFact} disabled={saving || !key.trim() || !value.trim()}>
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                保存
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <Brain className="h-4 w-4 text-primary" />
                长期事实（{facts.length}）
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-1.5">
              {facts.length === 0 && (
                <div className="py-4 text-center text-xs text-muted-foreground">
                  还没有事实，先添加一条
                </div>
              )}
              {facts.map((f) => (
                <div
                  key={f.key}
                  className="flex items-start gap-2 rounded-lg border border-border bg-muted/30 px-2.5 py-2"
                >
                  <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                    <span className="font-mono text-[11px] font-semibold text-primary">{f.key}</span>
                    <span className="truncate text-[13px] text-foreground">{f.value}</span>
                    <span className="text-[10px] text-muted-foreground">{relTime(f.updated_at)}</span>
                  </div>
                  <div className="flex flex-none items-center gap-1">
                    <button
                      className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                      title="编辑"
                      onClick={() => editFact(f)}
                    >
                      <Plus className="h-3 w-3 rotate-45" />
                    </button>
                    <button
                      className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-destructive/15 hover:text-destructive"
                      title="删除"
                      onClick={() => removeFact(f.key)}
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>


        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <Search className="h-4 w-4 text-primary" />
                向量记忆检索
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2.5">
              <div className="flex items-center gap-2">
                <Input
                  placeholder="按语义召回记忆，回车检索…"
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") doSearch();
                  }}
                />
                <Button onClick={doSearch} disabled={!q.trim()}>
                  <Search className="h-4 w-4" />
                  检索
                </Button>
              </div>
              {searched && (
                <div className="flex flex-col gap-1.5">
                  {hits.length === 0 && (
                    <div className="py-3 text-center text-xs text-muted-foreground">无结果</div>
                  )}
                  {hits.map((h, i) => (
                    <div key={i} className="rounded-lg border border-border bg-muted/30 px-2.5 py-2">
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-semibold text-primary">{h.source}</span>
                        <span className="font-mono text-[10px] text-muted-foreground">
                          score {(h.score * 100).toFixed(1)}%
                        </span>
                      </div>
                      <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{h.text}</p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <Brain className="h-4 w-4 text-primary" />
                上下文块预览（F4.3 上下文工程）
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2.5">
              <div className="flex items-center gap-2">
                <Input
                  placeholder="查询（可选，按语义召回）"
                  value={ctxQ}
                  onChange={(e) => setCtxQ(e.target.value)}
                />
                <label className="flex-none text-xs text-muted-foreground">预算</label>
                <Input
                  type="number"
                  value={budget}
                  onChange={(e) => setBudget(Number(e.target.value) || 1200)}
                  className="h-8 w-20"
                />
                <Button size="sm" onClick={doContext} disabled={ctxBusy}>
                  {ctxBusy ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Brain className="h-3.5 w-3.5" />
                  )}
                  生成
                </Button>
              </div>
              {block && (
                <pre className="max-h-72 overflow-y-auto whitespace-pre-wrap rounded-lg border border-border bg-muted/40 p-2.5 font-mono text-[11px] leading-relaxed text-foreground">
                  {block}
                </pre>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

