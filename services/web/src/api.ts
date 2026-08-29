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


// ---------- F1.3 人机协作审批 ----------

export interface ApprovalInfo {
  approval_id: string;
  task_id: string;
  tool_name: string;
  args: Record<string, unknown>;
  permission: string;
  description: string;
  status: string; // pending | approved | rejected | timed_out
  requested_at: number;
  decided_at: number | null;
  decided_by: string;
  reason: string;
}

export async function listApprovals(pendingOnly = false): Promise<ApprovalInfo[]> {
  const params = pendingOnly ? "?pending_only=true" : "";
  return json<ApprovalInfo[]>(await fetch("/v1/approvals" + params));
}

export async function decideApproval(
  approvalId: string,
  approved: boolean,
  reason = ""
): Promise<ApprovalInfo> {
  return json<ApprovalInfo>(
    await fetch("/v1/approvals/" + encodeURIComponent(approvalId) + "/decide", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved, reason }),
    })
  );
}


// ---------- 模型设置（控制台「模型」页） ----------

export interface ModelSettings {
  provider: string; // mock | openai
  base_url: string;
  model_name: string;
  has_api_key: boolean;
  api_key_source: string; // env | file | none
  configured: boolean;
}

export interface ModelPreset {
  id: string;
  name: string;
  provider: string;
  base_url: string;
  models: string[];
}

export interface ModelTestResult {
  ok: boolean;
  mode: string;
  models?: string[];
  error?: string;
}

export interface ModelConfigBody {
  provider?: string;
  base_url?: string;
  model_name?: string;
  api_key?: string;
}

export async function getModelSettings(): Promise<ModelSettings> {
  return json<ModelSettings>(await fetch("/v1/settings/model"));
}

export async function saveModelSettings(body: ModelConfigBody): Promise<ModelSettings> {
  return json<ModelSettings>(
    await fetch("/v1/settings/model", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  );
}

export async function getModelPresets(): Promise<ModelPreset[]> {
  return json<ModelPreset[]>(await fetch("/v1/settings/model/presets"));
}

export async function testModelConnection(body?: ModelConfigBody): Promise<ModelTestResult> {
  return json<ModelTestResult>(
    await fetch("/v1/settings/model/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body ?? {}),
    })
  );
}

// 自定义供应商（可保存多个，切换激活仍走 saveModelSettings）
export interface ModelProfile {
  id: string;
  name: string;
  provider: string;
  base_url: string;
  model_name: string;
  has_api_key: boolean;
}

export interface ModelProfileBody {
  id?: string;
  name?: string;
  provider?: string;
  base_url?: string;
  model_name?: string;
  api_key?: string;
}

export async function listModelProfiles(): Promise<ModelProfile[]> {
  return json<ModelProfile[]>(await fetch("/v1/settings/model/profiles"));
}

export async function saveModelProfile(body: ModelProfileBody): Promise<ModelProfile> {
  const { id, ...rest } = body;
  const method = id ? "PUT" : "POST";
  const url = id ? "/v1/settings/model/profiles/" + id : "/v1/settings/model/profiles";
  return json<ModelProfile>(
    await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(rest),
    })
  );
}

export async function deleteModelProfile(id: string): Promise<{ ok: boolean }> {
  return json<{ ok: boolean }>(
    await fetch("/v1/settings/model/profiles/" + id, { method: "DELETE" })
  );
}

