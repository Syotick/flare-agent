export interface TaskResult {
  status: string;
  output: string;
  step_count: number;
  message_count: number;
}

export interface TaskCreated {
  task_id: string;
  thread_id: string;
  status: string;
}

export interface StepEvent {
  type: string;
  node: string[];
  data: Record<string, any>;
}

export interface TaskDetail {
  task_id: string;
  thread_id: string;
  task_input: string;
  status: string;
  created_at: number;
  step_count: number;
  event_count: number;
  result: TaskResult | null;
  error: string | null;
}

async function json<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    const msg =
      body?.detail?.message ||
      body?.message ||
      "请求失败 (HTTP " + resp.status + ")";
    throw new Error(msg);
  }
  return resp.json() as Promise<T>;
}

export async function createTask(
  taskInput: string,
  maxSteps = 5,
  threadId?: string
): Promise<TaskCreated> {
  return json<TaskCreated>(
    await fetch("/v1/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_input: taskInput, max_steps: maxSteps, thread_id: threadId }),
    })
  );
}

export async function getTask(taskId: string): Promise<TaskDetail> {
  return json<TaskDetail>(await fetch("/v1/tasks/" + taskId));
}

export async function listTasks(): Promise<TaskDetail[]> {
  return json<TaskDetail[]>(await fetch("/v1/tasks"));
}
