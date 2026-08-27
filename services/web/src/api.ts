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
  result: TaskResult | null;
  error: string | null;
}

/** 提交任务（POST /v1/tasks），返回 task_id 等元信息。 */
export async function createTask(taskInput: string, maxSteps = 5): Promise<TaskCreated> {
  const resp = await fetch("/v1/tasks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_input: taskInput, max_steps: maxSteps }),
  });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    const msg = body?.detail?.message || body?.message || "请求失败 (HTTP " + resp.status + ")";
    throw new Error(msg);
  }
  return resp.json();
}
