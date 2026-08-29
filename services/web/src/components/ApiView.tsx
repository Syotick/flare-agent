import { useEffect, useState } from "react";
import { Copy, Loader2, Send, Terminal } from "lucide-react";
import { chatCompletions, listOpenAiModels, type OpenAiModel } from "../api";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

const CURL_EXAMPLE = `curl http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"flare-agent","messages":[{"role":"user","content":"帮我把周报拆成三点"}]}'`;

const CLI_EXAMPLE = `# CLI（安装后直接可用）
flare chat "帮我把周报拆成三点"           # 流式输出
flare --json chat "hello" --no-stream
flare tasks
flare models

# 或 python -m flare_cli
PYTHONPATH=services python -m flare_cli chat "你好"`;

const PYTHON_EXAMPLE = `from openai import OpenAI  # 任何 OpenAI SDK 零改造接入

client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="sk-xxx")
resp = client.chat.completions.create(
    model="flare-agent",
    messages=[{"role": "user", "content": "帮我把周报拆成三点"}],
)
print(resp.choices[0].message.content)`;

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="flex flex-none items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] text-muted-foreground hover:bg-muted hover:text-foreground"
      onClick={() => {
        void navigator.clipboard.writeText(text).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1200);
        });
      }}
    >
      <Copy className="h-3 w-3" />
      {copied ? "已复制" : "复制"}
    </button>
  );
}

export default function ApiView() {
  const [models, setModels] = useState<OpenAiModel[]>([]);
  const [prompt, setPrompt] = useState("帮我把周报拆成三点");
  const [calling, setCalling] = useState(false);
  const [response, setResponse] = useState<string>("");
  const [error, setError] = useState("");

  const refreshModels = async () => {
    try {
      setModels(await listOpenAiModels());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };
  useEffect(() => {
    refreshModels();
  }, []);

  const call = async () => {
    if (!prompt.trim() || calling) return;
    setCalling(true);
    setError("");
    setResponse("");
    try {
      const resp = await chatCompletions(prompt.trim());
      setResponse(JSON.stringify(resp, null, 2));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCalling(false);
    }
  };

  return (
    <div className="flex min-w-0 flex-1 flex-col gap-4 overflow-y-auto p-5">
      <div className="flex items-center gap-2">
        <Terminal className="h-5 w-5 text-primary" />
        <h1 className="text-lg font-semibold tracking-tight">开发者 API</h1>
        <span className="text-xs text-muted-foreground">OpenAI 兼容 Chat Completions · CLI · SDK 接入（F9.3）</span>
        <div className="ml-auto flex items-center gap-2">
          {models.length > 0 && (
            <span className="text-[11px] text-muted-foreground">
              模型：<span className="font-mono text-foreground">{models.map((m) => m.id).join(", ")}</span>
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">{error}</div>
      )}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {/* Playground */}
        <Card className="flex min-h-0 flex-col">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Send className="h-4 w-4 text-primary" />
              Playground
            </CardTitle>
            <span className="rounded-full bg-muted px-2 py-0.5 font-mono text-[10px] text-muted-foreground">POST /v1/chat/completions</span>
          </CardHeader>
          <CardContent className="flex flex-1 flex-col gap-3">
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              rows={4}
              className="w-full resize-none rounded-lg border border-border bg-input px-3 py-2 text-[13px] text-foreground outline-none placeholder:text-muted-foreground focus:border-primary/45"
              placeholder="输入任务描述…"
            />
            <Button onClick={call} disabled={calling || !prompt.trim()} className="self-start">
              {calling ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
              {calling ? "执行中…" : "调用"}
            </Button>
            {response && (
              <pre className="min-h-0 flex-1 overflow-y-auto whitespace-pre-wrap rounded-lg border border-border bg-muted/40 p-2.5 font-mono text-[11px] leading-relaxed text-foreground">
                {response}
              </pre>
            )}
          </CardContent>
        </Card>

        {/* 接入示例 */}
        <div className="flex flex-col gap-3">
          {[
            { title: "curl", code: CURL_EXAMPLE },
            { title: "CLI（flare）", code: CLI_EXAMPLE },
            { title: "OpenAI SDK", code: PYTHON_EXAMPLE },
          ].map((ex) => (
            <Card key={ex.title}>
              <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="text-sm">{ex.title}</CardTitle>
                <CopyButton text={ex.code} />
              </CardHeader>
              <CardContent>
                <pre className="overflow-x-auto whitespace-pre rounded-lg border border-border bg-muted/40 p-2.5 font-mono text-[11px] leading-relaxed text-foreground">
                  {ex.code}
                </pre>
              </CardContent>
            </Card>
          ))}
          <div className="rounded-lg border border-border bg-muted/30 px-3 py-2.5 text-[11px] text-muted-foreground">
            认证：服务端配置 FLARE_API_KEY 后，请求需带 <span className="font-mono">Authorization: Bearer &lt;key&gt;</span>；
            未配置则开放。默认开发端口 127.0.0.1:8000（/v1 前缀）。
          </div>
        </div>
      </div>
    </div>
  );
}
