import { useEffect, useState } from "react";
import { GitBranch, RefreshCw, Shield, Sparkles, Zap } from "lucide-react";
import FlareLogo from "./FlareLogo";

const GREETINGS = [
  "今天想让它帮你做什么？",
  "想让我读代码、写代码还是跑命令？",
  "选个工作区，我就能动手干活了",
  "有什么想让我在项目里完成的事？",
];

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
  const [g, setG] = useState(0);
  useEffect(() => {
    const t = window.setInterval(() => setG((v) => (v + 1) % GREETINGS.length), 3200);
    return () => window.clearInterval(t);
  }, []);

  return (
    <div className="mx-auto flex w-full max-w-[640px] flex-col items-center gap-7 px-6 pb-8 pt-14">
      {/* 渐变 Logo + 动态问候 */}
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="animate-flare-breathe relative">
          <div className="absolute -inset-6 rounded-full bg-primary/20 blur-2xl" />
          <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/30 to-accent/20 ring-1 ring-primary/30 shadow-[0_8px_40px_rgba(255,122,60,0.35)]">
            <FlareLogo size={40} animated />
          </div>
        </div>
        <div className="space-y-1.5">
          <h2 key={g} className="animate-fade-in-up text-[22px] font-bold tracking-tight text-gradient">
            {GREETINGS[g]}
          </h2>
          <p className="flex items-center justify-center gap-1.5 text-[13px] text-muted-foreground">
            <Sparkles className="h-3.5 w-3.5 text-primary/70" />
            输入任务直接开始，或点下面的示例快速体验
          </p>
        </div>
      </div>

      {/* 建议卡片：hover 上浮 + 图标微动 */}
      <div className="grid w-full grid-cols-1 gap-3 sm:grid-cols-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s.title}
            onClick={() => onPick(s.text)}
            className="group flex items-start gap-3 rounded-xl border border-border/80 bg-card/50 px-3.5 py-3 text-left backdrop-blur-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/40 hover:bg-card/80 hover:shadow-[0_8px_28px_rgba(255,122,60,0.16)]"
          >
            <span className="mt-0.5 flex h-8 w-8 flex-none items-center justify-center rounded-lg bg-primary/10 text-primary transition-all duration-200 group-hover:scale-110 group-hover:bg-primary/20 group-hover:shadow-[0_0_14px_rgba(255,122,60,0.35)]">
              {s.icon}
            </span>
            <span className="flex flex-col gap-0.5">
              <span className="text-[13px] font-semibold">{s.title}</span>
              <span className="text-[12px] leading-relaxed text-muted-foreground">{s.text}</span>
            </span>
          </button>
        ))}
      </div>

      <p className="text-[11px] text-muted-foreground/70">执行过程会以内联卡片展示，点击可查看详情 · 支持读代码 / 写代码 / 跑命令</p>
    </div>
  );
}
