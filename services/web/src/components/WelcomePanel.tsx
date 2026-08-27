import { GitBranch, RefreshCw, Shield, Zap } from "lucide-react";

const SUGGESTIONS = [
  {
    icon: <Zap className="h-4 w-4" />,
    title: "打个招呼",
    text: "帮我 echo 一句问候语，验证思考→调用→观察的链路",
  },
  {
    icon: <GitBranch className="h-4 w-4" />,
    title: "链式工具",
    text: "连续调用两次 echo，看 Agent 多步循环怎么走",
  },
  {
    icon: <Shield className="h-4 w-4" />,
    title: "预算封顶",
    text: "把最大步骤设为 3，让它跑一个超长任务看 budget_exceeded",
  },
  {
    icon: <RefreshCw className="h-4 w-4" />,
    title: "并发体验",
    text: "连续发多个任务，感受后台执行 + SSE 实时回流",
  },
];

export default function WelcomePanel({ onPick }: { onPick: (text: string) => void }) {
  return (
    <div className="mx-auto flex w-full max-w-[640px] flex-col items-center gap-6 px-6 pb-8 pt-16">
      <div className="flex flex-col items-center gap-2 text-center">
        <h2 className="text-2xl font-bold tracking-tight">今天想让它帮你做什么？</h2>
        <p className="text-[13px] text-muted-foreground">输入任务直接开始，或点下面的示例——它会调用工具、观察结果、给出结论</p>
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
      <p className="text-[11px] text-muted-foreground/80">提示：工具调用会以内联卡片展示，点开可看参数和输出</p>
    </div>
  );
}
