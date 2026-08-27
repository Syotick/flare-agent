import type { TaskResult } from "./api";

export interface ToolResult {
  ok: boolean;
  content: string;
  error_code: string | null;
  artifacts: Record<string, unknown>;
}

export interface AssistantMsg {
  text: string;
  done: boolean;
}

export type Item =
  | { id: number; kind: "user"; text: string }
  | { id: number; kind: "assistant"; msg: AssistantMsg }
  | {
      id: number;
      kind: "tool";
      name: string;
      args: Record<string, unknown>;
      status: "running" | "done";
      result?: ToolResult;
    }
  | { id: number; kind: "status"; text: string; tone: "info" | "warn" | "error" };

export interface Conversation {
  taskId?: string;
  items: Item[];
  tasks: TaskResult | null;
}
