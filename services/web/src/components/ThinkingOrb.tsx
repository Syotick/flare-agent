import { cn } from "../lib/utils";

// 思考光球：AI 干活时的呼吸光球（纯 CSS 层叠圆）
// 空闲慢呼吸；active（streaming）时加速脉冲 + 光环旋转
export default function ThinkingOrb({ active = false, size = 22 }: { active?: boolean; size?: number }) {
  return (
    <span
      className={cn("relative flex flex-none items-center justify-center", active ? "animate-orb-active" : "animate-orb-idle")}
      style={{ width: size, height: size }}
      aria-hidden
    >
      {/* 外光环（旋转） */}
      <span className="absolute inset-0 rounded-full border border-primary/40" style={{ borderTopColor: "transparent", borderBottomColor: "transparent" }} />
      {/* 主体：多层径向渐变光球 */}
      <span
        className="absolute inset-[18%] rounded-full"
        style={{
          background: "radial-gradient(circle at 35% 30%, #ffe2ae, #ff9d3c 45%, #e2441f 80%)",
          boxShadow: "0 0 14px rgba(255,157,60,0.55), inset 0 0 8px rgba(255,255,255,0.35)",
        }}
      />
      {/* 金色核心 */}
      <span className="absolute h-[30%] w-[30%] rounded-full" style={{ background: "#fff1c4", boxShadow: "0 0 6px rgba(255,241,196,0.9)" }} />
    </span>
  );
}
