import type { ApprovalInfo, TaskResult } from "./api";

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
  | { id: number; kind: "user"; text: string; ts?: number }
  | { id: number; kind: "assistant"; msg: AssistantMsg; ts?: number }
  | {
      id: number;
      kind: "tool";
      name: string;
      args: Record<string, unknown>;
      status: "running" | "done";
      result?: ToolResult;
      ts?: number;
    }
  | { id: number; kind: "status"; text: string; tone: "info" | "warn" | "error"; ts?: number }
  | { id: number; kind: "approval"; approval: ApprovalInfo; ts?: number };

export interface Conversation {
  taskId?: string;
  items: Item[];
  tasks: TaskResult | null;
}
