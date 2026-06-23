import {
  normalizeAgent,
  normalizeChatMessage,
  normalizeTask,
  normalizeTeam,
  type BackendAgent,
  type BackendChatMessage,
  type BackendQueueMessage,
  type BackendResponseData,
  type BackendTask,
  type BackendTeam,
} from "./pocketstudio-adapter";

const DEFAULT_API_BASE = "http://localhost:3777";
const STORAGE_KEY = "pocketstudio_api_base";

/** Resolve the API base URL. Priority: env > localStorage > default. */
export function getApiBase(): string {
  // Env var always wins (set at build time via NEXT_PUBLIC_*)
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window !== "undefined") {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return stored;
  }
  return DEFAULT_API_BASE;
}

/** Persist a custom API base URL in localStorage. Pass null to reset to default. */
export function setApiBase(url: string | null): void {
  if (url) {
    localStorage.setItem(STORAGE_KEY, url);
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
}

/** Check if the pocketStudio API is reachable at the given (or current) base URL. */
export async function checkConnection(baseUrl?: string): Promise<boolean> {
  const base = baseUrl ?? getApiBase();
  try {
    const res = await fetch(`${base}/api/health`, { signal: AbortSignal.timeout(3000) });
    return res.ok;
  } catch {
    return false;
  }
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const API_BASE = getApiBase();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(body.error || body.detail || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Types ─────────────────────────────────────────────────────────────────

export interface AgentConfig {
  name: string;
  provider: string;
  model: string;
  model_provider?: string;
  api_key?: string;
  working_directory: string;
  system_prompt?: string;
  prompt_file?: string;
  heartbeat?: {
    enabled?: boolean;
    interval?: number;
  };
}

export interface TeamConfig {
  name: string;
  agents: string[];
  leader_agent: string;
  mode?: "chain" | "fanout" | "workflow";
  max_rounds?: number;
}

export interface WorkflowNode {
  id: string;
  agentId?: string;
  prompt?: string;
  inputTemplate?: string;
  type?: string;
  routingFunction?: WorkflowRoutingFunction;
  [key: string]: unknown;
}

export interface WorkflowEdge {
  source: string;
  target: string;
  condition?: string;
  [key: string]: unknown;
}

export interface WorkflowRoute {
  condition: string;
  target: string;
}

export interface WorkflowRoutingFunction {
  language: "python";
  code: string;
  entrypoint: string;
}

export interface WorkflowConditionalEdge {
  source: string;
  routes: WorkflowRoute[];
}

export interface WorkflowDefinition {
  version?: number;
  entrypoint: string;
  outputNode?: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  conditionalEdges?: WorkflowConditionalEdge[];
  metadata?: Record<string, unknown>;
}

export interface TeamWorkflow {
  id: string;
  teamId: string;
  name: string;
  description: string;
  enabled: boolean;
  definition: WorkflowDefinition;
  createdAt?: string;
  updatedAt?: string;
}

export interface Settings {
  workspace?: { path?: string; name?: string };
  channels?: {
    enabled?: string[];
    discord?: { bot_token?: string };
    telegram?: { bot_token?: string };
    whatsapp?: Record<string, unknown>;
  };
  models?: {
    provider?: string;
    anthropic?: { model?: string; api_key?: string; oauth_token?: string };
    openai?: { model?: string; api_key?: string };
    opencode?: { model?: string };
  };
  build_in_model?: {
    model?: string;
    model_provider?: string;
    api_key?: string;
    temperature?: number;
    max_tokens?: number;
    timeout_seconds?: number;
  };
  agents?: Record<string, AgentConfig>;
  teams?: Record<string, TeamConfig>;
  monitoring?: { heartbeat_interval?: number };
}

export interface QueueStatus {
  incoming: number;
  queued: number;
  processing: number;
  outgoing: number;
  activeConversations: number;
}

export interface ProcessingMessage {
  id: number;
  messageId: string;
  channel: string;
  sender: string;
  message: string;
  agent: string;
  status: "queued" | "processing";
  processAlive: boolean;
  startedAt: number;
  duration: number;
}

export interface ResponseData {
  channel: string;
  sender: string;
  message: string;
  originalMessage: string;
  timestamp: number;
  messageId: string;
  agent?: string;
  files?: string[];
}

export interface EventData {
  type: string;
  timestamp: number;
  [key: string]: unknown;
}

export interface OfficeEvent extends EventData {
  eventId?: number;
  messageId?: string;
  agentId?: string;
  runId?: string;
  sessionId?: string;
  provider?: string;
  providerEventType?: string;
  summary?: string;
  content?: string;
  raw?: unknown;
  process?: unknown;
  target?: string;
  sender?: string;
  channel?: string;
  teamId?: string;
  fromAgent?: string;
  toAgent?: string;
  responseId?: number | string;
  status?: string;
  error?: string;
  tool?: string | null;
  delivered?: number;
}

export interface AgentMessage {
  id: number;
  agent_id: string;
  role: "user" | "assistant";
  channel: string;
  sender: string;
  message_id: string;
  content: string;
  created_at: number;
}

export function isInternalAgentInput(message: Pick<AgentMessage, "role" | "sender">): boolean {
  if (message.role !== "user") return false;
  return (
    message.sender === "System" ||
    message.sender === "orchestrator" ||
    message.sender.startsWith("workflow:") ||
    message.sender.startsWith("team:") ||
    message.sender.startsWith("chatroom:")
  );
}

// ── API Functions ─────────────────────────────────────────────────────────

export async function getAgents(): Promise<Record<string, AgentConfig>> {
  const agents = await apiFetch<BackendAgent[]>("/api/agents");
  return Object.fromEntries(agents.map((agent) => [agent.id, normalizeAgent(agent)]));
}

export async function getTeams(): Promise<Record<string, TeamConfig>> {
  const teams = await apiFetch<BackendTeam[]>("/api/teams");
  return Object.fromEntries(teams.map((team) => [team.id, normalizeTeam(team)]));
}

export async function getProviders(): Promise<string[]> {
  return apiFetch<string[]>("/api/providers");
}

export async function getSettings(): Promise<Settings> {
  return apiFetch<Settings>("/api/settings");
}

export async function searchRegistrySkills(
  agentId: string,
  query: string
): Promise<{ results: { ref: string; installs?: string; url?: string }[]; raw?: string }> {
  const q = encodeURIComponent(query);
  return apiFetch(`/api/agents/${encodeURIComponent(agentId)}/skills/registry?query=${q}`);
}

export async function installRegistrySkill(
  agentId: string,
  ref: string
): Promise<{ ok: boolean; output: string }> {
  return apiFetch(`/api/agents/${encodeURIComponent(agentId)}/skills/install`, {
    method: "POST",
    body: JSON.stringify({ ref }),
  });
}

export async function updateSettings(settings: Partial<Settings>): Promise<{ ok: boolean; settings: Settings }> {
  return apiFetch<{ ok: boolean; settings: Settings }>("/api/settings", {
    method: "PUT",
    body: JSON.stringify(settings),
  });
}

export async function runSetup(settings: Settings): Promise<{ ok: boolean; settings: Settings }> {
  return apiFetch("/api/setup", { method: "POST", body: JSON.stringify(settings) });
}

export async function applyServices(): Promise<{ ok: boolean; started: string[]; heartbeat: boolean; errors?: string[] }> {
  return apiFetch("/api/services/apply", { method: "POST" });
}

export async function getQueueStatus(): Promise<QueueStatus> {
  return apiFetch<QueueStatus>("/api/queue/status");
}

export async function getProcessingMessages(): Promise<ProcessingMessage[]> {
  return apiFetch<ProcessingMessage[]>("/api/queue/processing");
}

export async function killAgentSession(id: number): Promise<{ ok: boolean; agent: string; processKilled: boolean }> {
  return apiFetch(`/api/queue/processing/${encodeURIComponent(String(id))}/kill`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function getResponses(limit = 20): Promise<ResponseData[]> {
  return apiFetch<BackendResponseData[]>(`/api/responses?limit=${limit}`);
}

export async function getLogs(limit = 100): Promise<{ lines: string[] }> {
  return apiFetch(`/api/logs?limit=${limit}`);
}

export async function getOfficeEvents(limit = 200, since = 0): Promise<OfficeEvent[]> {
  const items = await apiFetch<Array<{ event?: string; data?: OfficeEvent }>>(
    `/api/events/office?limit=${limit}&since=${since}`,
  );
  return items
    .map((item) => item.data ?? null)
    .filter((event): event is OfficeEvent => Boolean(event));
}

export async function saveAgent(
  id: string,
  agent: Partial<AgentConfig> & Pick<AgentConfig, "name" | "provider" | "model">
): Promise<{ ok: boolean; agent: AgentConfig }> {
  const saved = await apiFetch<BackendAgent>("/api/agents", {
    method: "POST",
    body: JSON.stringify({
      id,
      name: agent.name,
      role: agent.system_prompt || agent.name,
      system_prompt: agent.system_prompt || "",
      provider: agent.provider,
      model: agent.model || null,
      model_provider: agent.model_provider || "",
      api_key: agent.api_key || "",
      workspace: agent.working_directory || null,
      enabled: true,
      heartbeat_enabled: agent.heartbeat?.enabled ?? true,
      heartbeat_interval: agent.heartbeat?.interval ?? null,
    }),
  });
  return { ok: true, agent: normalizeAgent(saved) };
}

export async function deleteAgent(id: string): Promise<{ ok: boolean }> {
  return apiFetch(`/api/agents/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export async function saveTeam(
  id: string,
  team: TeamConfig
): Promise<{ ok: boolean; team: TeamConfig }> {
  const saved = await apiFetch<BackendTeam>("/api/teams", {
    method: "POST",
    body: JSON.stringify({
      id,
      name: team.name,
      mode: team.mode || "chain",
      agent_ids: team.agents,
      leaderAgent: team.leader_agent || "",
      maxRounds: team.max_rounds ?? 1,
    }),
  });
  return { ok: true, team: normalizeTeam(saved) };
}

export async function deleteTeam(id: string): Promise<{ ok: boolean }> {
  return apiFetch(`/api/teams/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export async function getTeamWorkflows(teamId: string): Promise<TeamWorkflow[]> {
  return apiFetch<TeamWorkflow[]>(`/api/teams/${encodeURIComponent(teamId)}/workflows`);
}

export async function saveTeamWorkflow(
  teamId: string,
  workflowId: string,
  workflow: {
    name?: string;
    description?: string;
    definition?: WorkflowDefinition;
    enabled?: boolean;
  }
): Promise<TeamWorkflow> {
  const existing = await getTeamWorkflows(teamId);
  const method = existing.some((item) => item.id === workflowId) ? "PUT" : "POST";
  const path = method === "PUT"
    ? `/api/teams/${encodeURIComponent(teamId)}/workflows/${encodeURIComponent(workflowId)}`
    : `/api/teams/${encodeURIComponent(teamId)}/workflows`;
  return apiFetch<TeamWorkflow>(path, {
    method,
    body: JSON.stringify(method === "PUT" ? workflow : { id: workflowId, ...workflow }),
  });
}

export async function validateTeamWorkflow(
  teamId: string,
  definition: WorkflowDefinition
): Promise<{ ok: boolean; order: string[] }> {
  return apiFetch(`/api/teams/${encodeURIComponent(teamId)}/workflows/validate`, {
    method: "POST",
    body: JSON.stringify(definition),
  });
}

export async function importTeamWorkflow(
  teamId: string,
  artifact: Record<string, unknown>
): Promise<TeamWorkflow> {
  return apiFetch<TeamWorkflow>(`/api/teams/${encodeURIComponent(teamId)}/workflows/import`, {
    method: "POST",
    body: JSON.stringify(artifact),
  });
}

export async function exportTeamWorkflow(
  teamId: string,
  workflowId: string
): Promise<Record<string, unknown>> {
  return apiFetch(`/api/teams/${encodeURIComponent(teamId)}/workflows/${encodeURIComponent(workflowId)}/export`);
}

export async function sendMessage(payload: {
  message: string;
  agent?: string;
  sender?: string;
  channel?: string;
  projectId?: string;
}): Promise<{ ok: boolean; messageId: string }> {
  const targetMatch = payload.message.match(/^@(team:)?([a-zA-Z0-9_-]+)/);
  const explicitTeam = payload.agent?.startsWith("team:") ? payload.agent.slice("team:".length) : "";
  const agent = explicitTeam || payload.agent || targetMatch?.[2] || "pocketstudio";
  const target = explicitTeam || targetMatch?.[1] ? `@team:${agent}` : `@agent:${agent}`;
  const message = await apiFetch<BackendQueueMessage>("/api/messages", {
    method: "POST",
    body: JSON.stringify({
      target,
      content: payload.message.replace(/^@(team:)?[a-zA-Z0-9_-]+\s*/, ""),
      sender: payload.sender || "Web",
      metadata: payload.projectId ? { projectId: payload.projectId } : {},
    }),
  });
  return { ok: true, messageId: String(message.id) };
}

export async function getAgentMessages(
  agentId: string,
  limit = 100,
  sinceId = 0
): Promise<AgentMessage[]> {
  const params = new URLSearchParams({
    limit: String(limit),
    since_id: String(sinceId),
  });
  return apiFetch(`/api/agents/${encodeURIComponent(agentId)}/messages?${params.toString()}`);
}

// ── Agent Workspace Data ──────────────────────────────────────────────────

export interface WorkspaceSkill {
  id: string;
  name: string;
  description: string;
}

export async function getAgentSkills(agentId: string): Promise<WorkspaceSkill[]> {
  return apiFetch(`/api/agents/${encodeURIComponent(agentId)}/skills`);
}

export async function getAgentSystemPrompt(agentId: string): Promise<{ content: string; path: string }> {
  return apiFetch(`/api/agents/${encodeURIComponent(agentId)}/system-prompt`);
}

export async function saveAgentSystemPrompt(agentId: string, content: string): Promise<{ ok: boolean }> {
  return apiFetch(`/api/agents/${encodeURIComponent(agentId)}/system-prompt`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
}

export async function getAgentMemory(agentId: string): Promise<{ index: string; files: { name: string; path: string }[]; memoryDir: string }> {
  return apiFetch(`/api/agents/${encodeURIComponent(agentId)}/memory`);
}

export async function getAgentHeartbeat(agentId: string): Promise<{ content: string; path: string; enabled: boolean; interval?: number }> {
  return apiFetch<{ content: string; path: string; enabled: boolean; interval?: number }>(
    `/api/agents/${encodeURIComponent(agentId)}/heartbeat`
  );
}

export async function saveAgentHeartbeat(agentId: string, data: { content?: string; enabled?: boolean; interval?: number }): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(`/api/agents/${encodeURIComponent(agentId)}/heartbeat`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function resetAgentSession(agentId: string): Promise<{
  ok: boolean;
  agentId: string;
  cleared?: { messages?: number; responses?: number };
  providerReset?: boolean;
  nextRunReset?: boolean;
}> {
  return apiFetch(`/api/agents/${encodeURIComponent(agentId)}/reset`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

// ── Tasks ─────────────────────────────────────────────────────────────────

export type TaskStatus = "backlog" | "todo" | "in_progress" | "review" | "done";

export interface Task {
  id: string;
  number: number;
  identifier: string;
  title: string;
  description: string;
  status: TaskStatus;
  assignee: string;
  assigneeType: "agent" | "team" | "";
  projectId?: string;
  createdAt: number;
  updatedAt: number;
}

export async function getTasks(): Promise<Task[]> {
  const tasks = await apiFetch<BackendTask[]>("/api/tasks");
  return tasks.map(normalizeTask);
}

export async function createTask(task: Partial<Task>): Promise<{ ok: boolean; task: Task }> {
  const saved = await apiFetch<BackendTask>("/api/tasks", {
    method: "POST",
    body: JSON.stringify({
      title: task.title || "Untitled task",
      description: task.description || "",
      status: task.status || "todo",
      assignee: task.assignee || null,
      assigneeType: task.assigneeType || "",
      projectId: task.projectId || null,
    }),
  });
  return { ok: true, task: normalizeTask(saved) };
}

export async function updateTask(id: string, task: Partial<Task>): Promise<{ ok: boolean; task: Task }> {
  const updated = await apiFetch<BackendTask>(`/api/tasks/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify({
      title: task.title,
      description: task.description,
      status: task.status,
      assignee: task.assignee,
      assigneeType: task.assigneeType,
      projectId: task.projectId,
    }),
  });
  return { ok: true, task: normalizeTask(updated) };
}

export async function deleteTask(id: string): Promise<{ ok: boolean }> {
  await apiFetch(`/api/tasks/${encodeURIComponent(id)}`, { method: "DELETE" });
  return { ok: true };
}

export async function getTask(id: string): Promise<Task & { commentCount: number }> {
  const task = await apiFetch<BackendTask>(`/api/tasks/${encodeURIComponent(id)}`);
  return { ...normalizeTask(task), commentCount: task.commentCount || 0 };
}

export async function reorderTasks(columns: Record<string, string[]>): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>("/api/tasks/reorder", {
    method: "PUT",
    body: JSON.stringify({ columns }),
  });
}

// ── Comments ──────────────────────────────────────────────────────────────

export interface Comment {
  id: string;
  taskId: string;
  author: string;
  authorType: "user" | "agent";
  content: string;
  createdAt: number;
}

export async function getComments(taskId: string): Promise<Comment[]> {
  return apiFetch<Comment[]>(`/api/tasks/${encodeURIComponent(taskId)}/comments`);
}

export async function createComment(
  taskId: string,
  data: { author: string; authorType: "user" | "agent"; content: string }
): Promise<{ ok: boolean; comment: Comment }> {
  return apiFetch<{ ok: boolean; comment: Comment }>(`/api/tasks/${encodeURIComponent(taskId)}/comments`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteComment(id: string): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(`/api/comments/${encodeURIComponent(id)}`, { method: "DELETE" });
}

// ── Chat Room ────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: number;
  team_id: string;
  from_agent: string;
  message: string;
  client_message_id?: string | null;
  dispatch_status?: string | null;
  dispatch_queued_count?: number | null;
  dispatch_message_ids?: number[];
  created_at: number;
}

export async function getChatMessages(
  teamId: string,
  limit = 100,
  sinceId = 0
): Promise<ChatMessage[]> {
  const messages = await apiFetch<BackendChatMessage[]>(
    `/api/chatroom/${encodeURIComponent(teamId)}?limit=${limit}&since=${sinceId}`,
  );
  return messages.map(normalizeChatMessage);
}

export async function postChatMessage(
  teamId: string,
  message: string
): Promise<{ ok: boolean; messageId: number }> {
  const posted = await apiFetch<BackendChatMessage>(`/api/chatroom/${encodeURIComponent(teamId)}`, {
    method: "POST",
    body: JSON.stringify({ sender: "user", message }),
  });
  return { ok: true, messageId: posted.id };
}

export async function sendChatroomMessage(
  teamId: string,
  payload: { message: string; sender?: string; clientMessageId?: string },
): Promise<{ ok: boolean; chatMessage: ChatMessage; dispatch: { teamId: string; chatMessageId: number; queued: number; messageIds: number[] } | null }> {
  const response = await apiFetch<{ ok: boolean; chatMessage: BackendChatMessage; dispatch: { teamId: string; chatMessageId: number; queued: number; messageIds: number[] } | null }>(`/api/chatroom/${encodeURIComponent(teamId)}/send`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return { ...response, chatMessage: normalizeChatMessage(response.chatMessage) };
}

export async function dispatchTeamMessage(
  teamId: string,
  payload: { message: string; sender?: string; chatMessageId?: number },
): Promise<{ ok: boolean; teamId: string; queued: number; messageIds: number[] }> {
  return apiFetch(`/api/teams/${encodeURIComponent(teamId)}/dispatch`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// ── Projects ───────────────────────────────────────────────────────────

export interface Project {
  id: string;
  name: string;
  description: string;
  prefix: string;
  color: string;
  workspace?: string | null;
  status: "active" | "archived";
  createdAt: number;
  updatedAt: number;
}

export async function getProjects(): Promise<Project[]> {
  return apiFetch<Project[]>("/api/projects");
}

export async function createProject(
  data: Pick<Project, "name" | "description"> & Partial<Pick<Project, "workspace">>
): Promise<{ ok: boolean; project: Project }> {
  return apiFetch<{ ok: boolean; project: Project }>("/api/projects", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateProject(
  id: string,
  data: Partial<Omit<Project, "id" | "createdAt">>
): Promise<{ ok: boolean; project: Project }> {
  return apiFetch<{ ok: boolean; project: Project }>(`/api/projects/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteProject(id: string): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(`/api/projects/${encodeURIComponent(id)}`, { method: "DELETE" });
}

// ── Schedules ─────────────────────────────────────────────────────────────

export interface Schedule {
  id: string;
  label: string;
  cron: string;
  agentId: string;
  message: string;
  channel: string;
  sender: string;
  enabled: boolean;
  createdAt: number;
  runAt?: string;
}

export async function getSchedules(agentId?: string): Promise<Schedule[]> {
  const params = agentId ? `?agent=${encodeURIComponent(agentId)}` : "";
  return apiFetch(`/api/schedules${params}`);
}

export async function createSchedule(data: {
  cron?: string;
  runAt?: string;
  agentId: string;
  message: string;
  label?: string;
  channel?: string;
  sender?: string;
}): Promise<{ ok: boolean; schedule: Schedule }> {
  return apiFetch("/api/schedules", { method: "POST", body: JSON.stringify(data) });
}

export async function updateSchedule(
  id: string,
  data: Partial<Omit<Schedule, "id" | "createdAt">>
): Promise<{ ok: boolean; schedule: Schedule }> {
  return apiFetch(`/api/schedules/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteSchedule(id: string): Promise<{ ok: boolean }> {
  return apiFetch(`/api/schedules/${encodeURIComponent(id)}`, { method: "DELETE" });
}

// ── Control Plane ─────────────────────────────────────────────────────────

export async function getSystemStatus(): Promise<{
  ok: boolean;
  uptime: number;
  server: { running: boolean; port: number };
  channels: Record<string, { running: boolean; pid?: number }>;
  heartbeat: { running: boolean; interval: number; lastSent: Record<string, number> };
}> {
  return apiFetch("/api/status");
}

export async function restartService(): Promise<{ ok: boolean; action: string }> {
  return apiFetch("/api/services/restart", { method: "POST" });
}

export async function startChannel(channelId: string): Promise<{ ok: boolean }> {
  return apiFetch(`/api/services/channel/${encodeURIComponent(channelId)}/start`, { method: "POST" });
}

export async function stopChannel(channelId: string): Promise<{ ok: boolean }> {
  return apiFetch(`/api/services/channel/${encodeURIComponent(channelId)}/stop`, { method: "POST" });
}

export async function restartChannel(channelId: string): Promise<{ ok: boolean }> {
  return apiFetch(`/api/services/channel/${encodeURIComponent(channelId)}/restart`, { method: "POST" });
}

// ── Pairing ───────────────────────────────────────────────────────────────

export interface PairingPending {
  channel: string;
  senderId: string;
  sender: string;
  code: string;
  createdAt: number;
  lastSeenAt: number;
}

export interface PairingApproved {
  channel: string;
  senderId: string;
  sender: string;
  approvedAt: number;
  approvedCode?: string;
}

export interface PairingState {
  pending: PairingPending[];
  approved: PairingApproved[];
}

export async function getPairings(): Promise<PairingState> {
  return apiFetch("/api/pairing");
}

export async function approvePairing(code: string): Promise<{ ok: boolean; entry?: PairingApproved }> {
  return apiFetch("/api/pairing/approve", { method: "POST", body: JSON.stringify({ code }) });
}

export async function revokePairing(channel: string, senderId: string): Promise<{ ok: boolean }> {
  return apiFetch(`/api/pairing/${encodeURIComponent(channel)}/${encodeURIComponent(senderId)}`, { method: "DELETE" });
}

export async function dismissPending(code: string): Promise<{ ok: boolean }> {
  return apiFetch(`/api/pairing/pending/${encodeURIComponent(code)}`, { method: "DELETE" });
}

// ── Custom Providers ──────────────────────────────────────────────────────

export interface CustomProvider {
  name: string;
  harness: "openai" | "claude" | "codex";
  base_url: string;
  api_key: string;
  model?: string;
}

export async function getCustomProviders(): Promise<Record<string, CustomProvider>> {
  return apiFetch<Record<string, CustomProvider>>("/api/custom-providers");
}

export async function saveCustomProvider(id: string, provider: CustomProvider): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(`/api/custom-providers/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify(provider),
  });
}

export async function deleteCustomProvider(id: string): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(`/api/custom-providers/${encodeURIComponent(id)}`, { method: "DELETE" });
}

// ── SSE ───────────────────────────────────────────────────────────────────

export function subscribeToEvents(
  onEvent: (event: EventData) => void,
  onError?: (err: Event) => void,
  eventTypes?: string[]
): () => void {
  const es = new EventSource(`${getApiBase()}/api/events/stream`);

  const handler = (e: MessageEvent) => {
    try { onEvent(JSON.parse(e.data)); } catch { /* ignore parse errors */ }
  };

  // Listen to all known event types
  const types = eventTypes ?? [
    "message:incoming", "message:processing", "message:done", "message:failed",
    "agent:invoke", "agent:progress", "agent:response", "agent:mention",
    "agent:stdout", "agent:stderr", "agent:tool_call", "agent:tool_result",
    "response:queued", "chat:posted", "team:chatroom",
  ];
  for (const type of types) {
    es.addEventListener(type, handler);
  }

  if (onError) es.onerror = onError;

  return () => es.close();
}
