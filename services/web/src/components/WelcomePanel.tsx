import { GitBranch, RefreshCw, Shield, Zap } from "lucide-react";

const SUGGESTIONS = [
  {
    icon: <Zap className="h-4 w-4" />,
    title: "打个招呼",
    text: "帮我打个招呼",
  },
  {
    icon: <GitBranch className="h-4 w-4" />,
    title: "多步任务",
    text: "连续做两件事，看它一步步完成",
  },
  {
    icon: <Shield className="h-4 w-4" />,
    title: "分步执行",
    text: "让它把任务拆成几步完成",
  },
  {
    icon: <RefreshCw className="h-4 w-4" />,
    title: "并行处理",
    text: "一次发多个任务，看它并行处理",
  },
];

export default function WelcomePanel({ onPick }: { onPick: (text: string) => void }) {
  return (
    <div className="mx-auto flex w-full max-w-[640px] flex-col items-center gap-6 px-6 pb-8 pt-16">
      <div className="flex flex-col items-center gap-2 text-center">
        <h2 className="text-2xl font-bold tracking-tight">今天想让它帮你做什么？</h2>
        <p className="text-[13px] text-muted-foreground">输入任务直接开始，或点下面的示例快速体验</p>
      </div>
      <div className="grid w-full grid-cols-1 gap-2.5 sm:grid-cols-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s.title}
            onClick={() => onPick(s.text)}
            className="group flex items-start gap-3 rounded-xl border border-border/80 bg-card/50 px-3.5 py-3 text-left backdrop-blur-sm transition-all hover:border-primary/40 hover:bg-card/80 hover:shadow-[0_4px_20px_rgba(255,122,60,0.12)]"
          >
            <span className="mt-0.5 flex h-8 w-8 flex-none items-center justify-center rounded-lg bg-primary/10 text-primary transition-colors group-hover:bg-primary/20">
              {s.icon}
            </span>
            <span className="flex flex-col gap-0.5">
              <span className="text-[13px] font-semibold">{s.title}</span>
              <span className="text-[12px] leading-relaxed text-muted-foreground">{s.text}</span>
            </span>
          </button>
        ))}
      </div>
      <p className="text-[11px] text-muted-foreground/80">提示：执行过程会以内联卡片展示，点击可查看详情</p>
    </div>
  );
}
