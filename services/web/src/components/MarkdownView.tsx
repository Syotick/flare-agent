import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { Check, Copy } from "lucide-react";

// Markdown 渲染（含 GFM 表格/任务列表 + 代码高亮 + 语言标签 + 复制按钮）。
// 纯展示组件：streaming 阶段用 StreamText 纯文本打字机，done 后切本组件全量渲染。

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard 不可用时静默
    }
  };
  return (
    <button
      onClick={copy}
      className="rounded-md p-1 text-muted-foreground/70 transition-colors hover:bg-muted hover:text-foreground"
      title="复制代码"
    >
      {copied ? <Check className="h-3 w-3 text-success" /> : <Copy className="h-3 w-3" />}
    </button>
  );
}

// 从 code 元素提取语言与纯文本（供复制按钮）
function extractCodeInfo(node: unknown): { lang: string; text: string } {
  const codeNode = (node as { children?: unknown[] } | undefined)?.children?.[0] as
    | { type?: string; properties?: { className?: unknown }; children?: unknown[] }
    | undefined;
  if (!codeNode) return { lang: "text", text: "" };
  const cls = codeNode.properties?.className;
  const lang =
    (Array.isArray(cls) ? cls.join(" ") : String(cls || "")).match(/language-([\w-]+)/)?.[1] || "text";
  const text = (codeNode.children ?? [])
    .map((c) => ((c as { type?: string; value?: string }).type === "text" ? (c as { value: string }).value : ""))
    .join("");
  return { lang, text };
}

export default function MarkdownView({ text }: { text: string }) {
  return (
    <div className="markdown-body min-w-0">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={{
          pre({ node, children }) {
            const { lang, text: raw } = extractCodeInfo(node);
            return (
              <div className="group relative my-2 overflow-hidden rounded-xl border border-border bg-[#0d0a08]">
                <div className="flex items-center justify-between border-b border-border/70 bg-[#14100d] px-3 py-1.5">
                  <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{lang}</span>
                  <CopyButton text={raw} />
                </div>
                <pre className="overflow-x-auto p-3 font-mono text-[12.5px] leading-relaxed text-[#f0e6da]">
                  {children}
                </pre>
              </div>
            );
          },
          code({ node, className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || "");
            const isBlock = !!match || String(children).includes("\n");
            if (isBlock) {
              return (
                <code className={className} {...props}>
                  {children}
                </code>
              );
            }
            return (
              <code
                className="rounded-md bg-primary/12 px-1.5 py-0.5 font-mono text-[0.85em] text-[#ffd9a0]"
                {...props}
              >
                {children}
              </code>
            );
          },
          a({ href, children }) {
            return (
              <a href={href} target="_blank" rel="noreferrer" className="text-primary underline decoration-primary/40 underline-offset-2 transition-colors hover:decoration-primary">
                {children}
              </a>
            );
          },
          table({ children }) {
            return (
              <div className="my-2 overflow-x-auto rounded-lg border border-border">
                <table className="w-full text-[12.5px]">{children}</table>
              </div>
            );
          },
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
