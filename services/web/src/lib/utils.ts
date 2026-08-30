import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// 相对时间（刚刚/N 分钟前/N 小时前/月-日）
export function relTime(ts: number): string {
  const ms = Date.now() - ts * 1000;
  if (ms < 60000) return "刚刚";
  if (ms < 3600000) return Math.floor(ms / 60000) + " 分钟前";
  if (ms < 86400000) return Math.floor(ms / 3600000) + " 小时前";
  const d = new Date(ts * 1000);
  return d.getMonth() + 1 + "/" + d.getDate();
}

// 工作区显示名：路径取最后一段（Windows 盘符如 "C:\" 保持原样）
export function workspaceLabel(id: string): string {
  if (!id) return "";
  if (/^[A-Za-z]:[\\/]?$/.test(id)) return id.toUpperCase();
  const norm = id.replace(/[\\/]+$/, "");
  const idx = Math.max(norm.lastIndexOf("/"), norm.lastIndexOf("\\"));
  return idx >= 0 ? norm.slice(idx + 1) : norm;
}

// 自动标题（截断长文本）
export function autoTitle(text: string): string {
  const t = text.trim().replace(/\s+/g, " ");
  return t.length > 24 ? t.slice(0, 24) + "…" : t || "新会话";
}

// 按日期分组：今天/昨天/近 7 天/更早
export function groupByDate<T extends { created_at: number }>(
  items: T[]
): { label: string; items: T[] }[] {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const day = 86400000;
  const buckets: [string, (t: T) => boolean][] = [
    ["今天", (t) => t.created_at >= start],
    ["昨天", (t) => t.created_at >= start - day && t.created_at < start],
    ["近 7 天", (t) => t.created_at >= start - 7 * day && t.created_at < start - day],
    ["更早", (t) => t.created_at < start - 7 * day],
  ];
  const out: { label: string; items: T[] }[] = [];
  for (const [label, pred] of buckets) {
    const picked = items.filter(pred);
    if (picked.length > 0) out.push({ label, items: picked });
  }
  return out;
}
