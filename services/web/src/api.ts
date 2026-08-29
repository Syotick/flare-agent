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

export async function deleteTask(taskId: string): Promise<void> {
  const resp = await fetch("/v1/tasks/" + taskId, { method: "DELETE" });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    const msg =
      body?.detail?.message || "删除失败 (HTTP " + resp.status + ")";
    throw new Error(msg);
  }
}


// ---------- M3a 知识库 ----------

export interface DocumentSummary {
  doc_id: string;
  title: string;
  created_at: number;
}

export interface IngestResponse {
  doc_id: string;
  title: string;
  chunk_count: number;
  chars: number;
}

export interface SearchHit {
  doc_id: string;
  title: string;
  chunk_index: number;
  text: string;
  score: number;
}

export interface EvalStrategyOut {
  strategy: string;
  k: number;
  aggregate: Record<string, number>;
  per_query: Record<string, unknown>[];
}

export interface EvalResponse {
  dataset: string;
  k: number;
  strategies: EvalStrategyOut[];
  skipped: Record<string, unknown>[];
  ragas: Record<string, unknown> | null;
}

export async function listDocuments(): Promise<DocumentSummary[]> {
  return json<DocumentSummary[]>(await fetch("/v1/kb/documents"));
}

export async function ingestDocument(title: string, content: string): Promise<IngestResponse> {
  return json<IngestResponse>(
    await fetch("/v1/kb/documents", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, content }),
    })
  );
}

export async function deleteDocument(docId: string): Promise<void> {
  const resp = await fetch("/v1/kb/documents/" + encodeURIComponent(docId), { method: "DELETE" });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body?.detail?.message || "删除失败 (HTTP " + resp.status + ")");
  }
}

export async function searchKnowledgeBase(q: string, k = 5): Promise<SearchHit[]> {
  const params = new URLSearchParams({ q, k: String(k) });
  return json<SearchHit[]>(await fetch("/v1/kb/search?" + params));
}

export async function runEval(body: {
  k: number;
  judge: string;
  strategies?: string[];
}): Promise<EvalResponse> {
  return json<EvalResponse>(
    await fetch("/v1/kb/eval", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  );
}

// ---------- M3b 记忆 ----------

export interface Fact {
  project_id: string;
  key: string;
  value: string;
  updated_at: number;
}

export interface MemoryHit {
  source: string;
  text: string;
  score: number;
}

export async function listFacts(): Promise<Fact[]> {
  return json<Fact[]>(await fetch("/v1/memory/facts"));
}

export async function putFact(key: string, value: string): Promise<Fact> {
  return json<Fact>(
    await fetch("/v1/memory/facts/" + encodeURIComponent(key), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value }),
    })
  );
}

export async function deleteFact(key: string): Promise<void> {
  const resp = await fetch("/v1/memory/facts/" + encodeURIComponent(key), { method: "DELETE" });
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body?.detail?.message || "删除失败 (HTTP " + resp.status + ")");
  }
}

export async function searchMemory(q: string, k = 4): Promise<MemoryHit[]> {
  const resp = await json<{ hits: MemoryHit[] }>(
    await fetch("/v1/memory/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ q, k }),
    })
  );
  return resp.hits;
}

export async function getMemoryContext(q = "", budget = 1200): Promise<string> {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  params.set("budget", String(budget));
  const resp = await json<{ block: string }>(await fetch("/v1/memory/context?" + params));
  return resp.block;
}


// ---------- M6 运维 ----------

export type AlertSeverity = "none" | "warning" | "critical";

export interface SloBudget {
  slo: string;
  target: number;
  total: number;
  bad: number;
  budget: number;
  consumed_ratio: number;
  remaining_ratio: number;
}

export interface SloAlert {
  severity: AlertSeverity;
  name: string;
  message: string;
}

export interface SloEntry {
  name: string;
  target: number;
  budget?: SloBudget;
  p95?: number | null;
  alert: SloAlert;
}

export interface SloStatus {
  overall: AlertSeverity;
  generated_at: number;
  period_days: number;
  slos: SloEntry[];
}

export async function getSloStatus(): Promise<SloStatus> {
  return json<SloStatus>(await fetch("/v1/ops/slo"));
}

export async function getMetricsText(): Promise<string> {
  const resp = await fetch("/metrics");
  return resp.text();
}


// ---------- 能力盘点（前端入口闭环：MCP/Skills/多 Agent/工具注册表） ----------

export interface ToolInfo {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

export interface SkillInfo {
  name: string;
  description: string;
  required_tools: string[];
  resource_count: number;
}

export interface SkillDetail {
  name: string;
  description: string;
  instructions: string;
  required_tools: string[];
  resources: Record<string, string>;
}

export interface McpServerStatus {
  name: string;
  transport: string;
  enabled: boolean;
  connected: boolean;
  tools_registered: string[];
}

export interface SubagentRecord {
  subagent_id: string;
  prompt: string;
  status: string;
  output: string;
  error: string | null;
  step_count: number;
  created_at: number;
}

export interface SubagentStatus {
  active_count: number;
  records: SubagentRecord[];
}

export async function listTools(): Promise<ToolInfo[]> {
  return json<ToolInfo[]>(await fetch("/v1/capabilities/tools"));
}

export async function listSkills(): Promise<SkillInfo[]> {
  return json<SkillInfo[]>(await fetch("/v1/capabilities/skills"));
}

export async function getSkill(name: string): Promise<SkillDetail> {
  return json<SkillDetail>(await fetch("/v1/capabilities/skills/" + encodeURIComponent(name)));
}

export async function listMcpServers(): Promise<McpServerStatus[]> {
  return json<McpServerStatus[]>(await fetch("/v1/capabilities/mcp"));
}

export async function getSubagentStatus(): Promise<SubagentStatus> {
  return json<SubagentStatus>(await fetch("/v1/capabilities/subagent"));
}


// ---------- F9.3 OpenAI 兼容 API（开发者入口 playground） ----------

export interface OpenAiModel {
  id: string;
  object: string;
  owned_by: string;
}

export async function listOpenAiModels(): Promise<OpenAiModel[]> {
  const resp = await json<{ data: OpenAiModel[] }>(await fetch("/v1/models"));
  return resp.data;
}

export async function chatCompletions(prompt: string): Promise<Record<string, unknown>> {
  return json<Record<string, unknown>>(
    await fetch("/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "flare-agent",
        messages: [{ role: "user", content: prompt }],
        stream: false,
      }),
    })
  );
}

