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

// ── API Functions ─────────────────────────────────────────────────────────

export async function getAgents(): Promise<Record<string, AgentConfig>> {
  const agents = await apiFetch<BackendAgent[]>("/api/agents");
  return Object.fromEntries(agents.map((agent) => [agent.id, normalizeAgent(agent)]));
}

export async function getTeams(): Promise<Record<string, TeamConfig>> {
  const teams = await apiFetch<BackendTeam[]>("/api/teams");
  return Object.fromEntries(teams.map((team) => [team.id, normalizeTeam(team)]));
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
      mode: "chain",
      agent_ids: team.agents,
      leaderAgent: team.leader_agent || "",
    }),
  });
  return { ok: true, team: normalizeTeam(saved) };
}

export async function deleteTeam(id: string): Promise<{ ok: boolean }> {
  return apiFetch(`/api/teams/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export async function sendMessage(payload: {
  message: string;
  agent?: string;
  sender?: string;
  channel?: string;
}): Promise<{ ok: boolean; messageId: string }> {
  const targetMatch = payload.message.match(/^@(team:)?([a-zA-Z0-9_-]+)/);
  const agent = payload.agent || targetMatch?.[2] || "pocketstudio";
  const target = targetMatch?.[1] ? `@team:${agent}` : `@agent:${agent}`;
  const message = await apiFetch<BackendQueueMessage>("/api/messages", {
    method: "POST",
    body: JSON.stringify({
      target,
      content: payload.message.replace(/^@(team:)?[a-zA-Z0-9_-]+\s*/, ""),
      sender: payload.sender || "Web",
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
): Promise<{ ok: boolean }> {
  await apiFetch(`/api/chatroom/${encodeURIComponent(teamId)}`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
  return { ok: true };
}

// ── Projects ───────────────────────────────────────────────────────────

export interface Project {
  id: string;
  name: string;
  description: string;
  prefix: string;
  color: string;
  status: "active" | "archived";
  createdAt: number;
  updatedAt: number;
}

export async function getProjects(): Promise<Project[]> {
  return apiFetch<Project[]>("/api/projects");
}

export async function createProject(
  data: Pick<Project, "name" | "description">
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
    "message:incoming", "agent:invoke", "agent:progress",
    "agent:response", "agent:mention", "message:done",
  ];
  for (const type of types) {
    es.addEventListener(type, handler);
  }

  if (onError) es.onerror = onError;

  return () => es.close();
}
