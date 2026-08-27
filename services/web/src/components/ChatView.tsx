import { useEffect, useRef, useState } from "react";
import { cn } from "../lib/utils";
import type { Item } from "../types";
import FlareLogo from "./FlareLogo";
import ThinkingOrb from "./ThinkingOrb";
import ToolCallCard from "./ToolCallCard";
import WelcomePanel from "./WelcomePanel";

// 打字机流式文本
function StreamText({ text, done }: { text: string; done: boolean }) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    setShown(0);
  }, [text]);
  useEffect(() => {
    if (done || shown >= text.length) return;
    const t = window.setTimeout(() => setShown((s) => Math.min(s + 2, text.length)), 12);
    return () => window.clearTimeout(t);
  }, [shown, done, text]);
  return (
    <span>
      {text.slice(0, shown)}
      {!done && <span className="ml-0.5 inline-block h-[1em] w-[2px] animate-pulse bg-primary" />}
    </span>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] whitespace-pre-wrap break-words rounded-2xl rounded-br-sm border border-border bg-secondary px-4 py-2.5 text-[14px] leading-relaxed">
        {text}
      </div>
    </div>
  );
}

function AssistantBubble({ text, done }: { text: string; done: boolean }) {
  return (
    <div className="flex items-start gap-2.5">
      <FlareLogo size={22} animated={!done} className="mt-1" />
      <div className="whitespace-pre-wrap break-words rounded-2xl rounded-bl-sm px-1 py-0.5 text-[14px] leading-relaxed">
        <StreamText text={text} done={done} />
      </div>
    </div>
  );
}

function StatusLine({ text, tone }: { text: string; tone: "info" | "warn" | "error" }) {
  return (
    <div className={cn("font-mono text-xs", tone === "error" ? "text-destructive" : tone === "warn" ? "text-warning" : "text-muted-foreground")}>
      {text}
    </div>
  );
}

function renderItem(it: Item) {
  switch (it.kind) {
    case "user":
      return <UserBubble key={it.id} text={it.text} />;
    case "assistant":
      return <AssistantBubble key={it.id} text={it.msg.text} done={it.msg.done} />;
    case "tool":
      return (
        <ToolCallCard key={it.id} name={it.name} args={it.args} status={it.status} result={it.result} />
      );
    case "status":
      return <StatusLine key={it.id} text={it.text} tone={it.tone} />;
  }
}

export default function ChatView({ items, running, onPick }: { items: Item[]; running: boolean; onPick: (text: string) => void }) {
  const endRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [items.length]);
  const hasContent = items.length > 0;
  return (
    <div className="flex-1 overflow-y-auto">
      {!hasContent ? (
        <WelcomePanel onPick={onPick} />
      ) : (
        <div className="mx-auto flex w-full max-w-[820px] flex-col gap-3 px-6 py-6 pb-8">
          {items.map((it) => renderItem(it))}
          {running && (
            <div className="flex items-center gap-2 text-[13px] text-muted-foreground">
              <ThinkingOrb active size={16} />
              <span>思考中…</span>
            </div>
          )}
          <div ref={endRef} />
        </div>
      )}
    </div>
  );
}
