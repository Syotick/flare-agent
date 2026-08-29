import { useEffect, useState } from "react";
import { FlaskConical, FileText, Loader2, RefreshCw, Search, Trash2, Upload } from "lucide-react";
import {
  deleteDocument,
  ingestDocument,
  listDocuments,
  runEval,
  searchKnowledgeBase,
  type DocumentSummary,
  type EvalResponse,
  type SearchHit,
} from "../api";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Input, Textarea } from "./ui/input";
import { relTime } from "../lib/utils";

function metricLabel(key: string): string {
  return key.replace(/_/g, " ").replace(/\b(\w)/g, (c) => c.toUpperCase());
}

export default function KnowledgeBaseView() {
  const [docs, setDocs] = useState<DocumentSummary[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [searched, setSearched] = useState(false);
  const [evalK, setEvalK] = useState(5);
  const [evalResp, setEvalResp] = useState<EvalResponse | null>(null);
  const [evalBusy, setEvalBusy] = useState(false);

  const refresh = () => {
    listDocuments()
      .then(setDocs)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  };
  useEffect(() => {
    refresh();
  }, []);

  const doIngest = async () => {
    if (!title.trim() || !content.trim() || busy) return;
    setBusy(true);
    setError("");
    setOk("");
    try {
      const r = await ingestDocument(title.trim(), content.trim());
      setOk("已入库「" + r.title + "」，共 " + r.chunk_count + " 段");
      setTitle("");
      setContent("");
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const doDelete = async (docId: string) => {
    setError("");
    setOk("");
    try {
      await deleteDocument(docId);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const doSearch = async () => {
    if (!q.trim()) return;
    setError("");
    try {
      setHits(await searchKnowledgeBase(q.trim(), 8));
      setSearched(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const doEval = async () => {
    setEvalBusy(true);
    setError("");
    try {
      setEvalResp(await runEval({ k: evalK, judge: "proxy" }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setEvalBusy(false);
    }
  };

  return (

    <div className="flex min-w-0 flex-1 flex-col gap-4 overflow-y-auto p-5">
      <div className="flex items-center gap-2">
        <FileText className="h-5 w-5 text-primary" />
        <h1 className="text-lg font-semibold tracking-tight">知识库管理</h1>
        <span className="text-xs text-muted-foreground">入库 / 检索 / 评测</span>
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
                <Upload className="h-4 w-4 text-primary" />
                入库文档
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2.5">
              <Input
                placeholder="标题（如：部署指南）"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
              <Textarea
                placeholder="正文（自动分块入库；不超过 10 万字符）"
                value={content}
                onChange={(e) => setContent(e.target.value)}
              />
              <Button onClick={doIngest} disabled={busy || !title.trim() || !content.trim()}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                入库
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <FileText className="h-4 w-4 text-primary" />
                文档（{docs.length}）
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-1.5">
              {docs.length === 0 && (
                <div className="py-4 text-center text-xs text-muted-foreground">
                  知识库为空，先入库一份文档
                </div>
              )}
              {docs.map((d) => (
                <div
                  key={d.doc_id}
                  className="flex items-center gap-2 rounded-lg border border-border bg-muted/30 px-2.5 py-2"
                >
                  <div className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate text-[13px] text-foreground">{d.title}</span>
                    <span className="text-[10px] text-muted-foreground">
                      {relTime(d.created_at)}
                    </span>
                  </div>
                  <button
                    className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-destructive/15 hover:text-destructive"
                    title="删除文档"
                    onClick={() => doDelete(d.doc_id)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
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
                检索（hybrid 混合检索）
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2.5">
              <div className="flex items-center gap-2">
                <Input
                  placeholder="输入查询，回车检索…"
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
                        <span className="text-[11px] font-semibold text-primary">{h.title}</span>
                        <span className="font-mono text-[10px] text-muted-foreground">
                          #{h.chunk_index} · score {(h.score * 100).toFixed(1)}%
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
                <FlaskConical className="h-4 w-4 text-primary" />
                RAG 评测（proxy 判定，无需真模型）
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2.5">
              <div className="flex items-center gap-2">
                <label className="text-xs text-muted-foreground">k</label>
                <Input
                  type="number"
                  min={1}
                  max={20}
                  value={evalK}
                  onChange={(e) => setEvalK(Number(e.target.value) || 5)}
                  className="h-8 w-20"
                />
                <Button size="sm" onClick={doEval} disabled={evalBusy}>
                  {evalBusy ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <FlaskConical className="h-3.5 w-3.5" />
                  )}
                  运行评测
                </Button>
              </div>
              {evalResp && (
                <div className="flex flex-col gap-2">
                  {evalResp.strategies.map((s) => (
                    <div key={s.strategy} className="rounded-lg border border-border bg-muted/30 px-2.5 py-2">
                      <div className="mb-1 flex items-center gap-2">
                        <span className="font-mono text-[11px] font-semibold text-primary">{s.strategy}</span>
                        <span className="text-[10px] text-muted-foreground">
                          dataset={evalResp.dataset} k={s.k}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5">
                        {Object.entries(s.aggregate || {}).map(([k2, v]) => (
                          <span key={k2} className="flex items-center justify-between text-[11px]">
                            <span className="text-muted-foreground">{metricLabel(k2)}</span>
                            <span className="font-mono text-foreground">
                              {typeof v === "number" ? v.toFixed(3) : String(v)}
                            </span>
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                  {evalResp.skipped && evalResp.skipped.length > 0 && (
                    <div className="text-[11px] text-warning">
                      skipped {evalResp.skipped.length}（相关文档未入库的 case 不计分，诚实报告）
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

