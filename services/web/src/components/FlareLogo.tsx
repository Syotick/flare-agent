import { cn } from "../lib/utils";

// 耀斑 Logo：太阳本体(琥珀金光球) + 日珥轨道环(绕行灰烬光点) + 金色核心
// 寓意 agent loop：思考→行动闭环；animated 时轨道绕行 + 日冕呼吸
export default function FlareLogo({ size = 32, animated = false, className }: { size?: number; animated?: boolean; className?: string }) {
  const gid = "flare-" + size + (animated ? "-a" : "-s");
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" className={cn("flex-none", className)} aria-label="Flare">
      <defs>
        <linearGradient id={gid + "-sun"} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#ffd68a" />
          <stop offset="45%" stopColor="#ff9d3c" />
          <stop offset="100%" stopColor="#e2441f" />
        </linearGradient>
        <radialGradient id={gid + "-glow"} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#ffd68a" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#ffd68a" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* 背景微光 */}
      <circle cx="32" cy="32" r="26" fill={"url(#" + gid + "-glow)"} opacity="0.35" />

      {/* 日珥轨道环 + 绕行灰烬光点 */}
      <g className={animated ? "origin-center animate-spin-slow" : undefined}>
        <ellipse cx="32" cy="32" rx="27" ry="11" fill="none" stroke="#ff7a3c" strokeOpacity="0.45" strokeWidth="1.5" transform="rotate(-24 32 32)" />
        <circle cx="59" cy="32" r="2.4" fill="#ffd68a" transform="rotate(-24 32 32) translate(27 0) rotate(24 32 32)" opacity={animated ? 1 : 0.85} />
      </g>

      {/* 太阳本体：外圈日珥 + 内圈光球 + 金色核心 */}
      <g className={animated ? "origin-center animate-flare-breathe" : undefined}>
        <circle cx="32" cy="32" r="15" fill={"url(#" + gid + "-sun)"} />
        <circle cx="32" cy="32" r="9.5" fill="#ffc46b" opacity="0.55" />
        <circle cx="32" cy="32" r="5" fill="#fff1c4" />
      </g>
    </svg>
  );
}
