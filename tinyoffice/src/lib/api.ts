const DEFAULT_API_BASE = "http://localhost:3777";
const STORAGE_KEY = "tinyagi_api_base";

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

/** Check if the TinyAGI API is reachable at the given (or current) base URL. */
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

type LocalAgent = {
  id: string;
  name: string;
  role: string;
  system_prompt?: string;
  provider: string;
  model?: string | null;
  workspace?: string;
  enabled?: boolean;
};

type LocalTeam = {
  id: string;
  name: string;
  mode: "chain" | "fanout";
  agent_ids: string[];
};

type LocalQueueMessage = {
  id: number;
  target: string;
  content: string;
  sender: string;
  status: "queued" | "running" | "done" | "failed" | "dead";
  attempts: number;
  error?: string | null;
  result?: string | null;
  created_at: string;
  updated_at: string;
};

type LocalTask = {
  id: number;
  title: string;
  description: string;
  status: string;
  assignee?: string | null;
  created_at: string;
  updated_at: string;
};

function toTimestamp(value?: string | number | null): number {
  if (typeof value === "number") return value;
  if (!value) return Date.now();
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : Date.now();
}

function normalizeAgent(agent: LocalAgent): AgentConfig {
  return {
    name: agent.name,
    provider: agent.provider || "local",
    model: agent.model || "",
    working_directory: agent.workspace || "",
    system_prompt: agent.system_prompt || agent.role || "",
  };
}

function normalizeTeam(team: LocalTeam): TeamConfig {
  return {
    name: team.name,
    agents: team.agent_ids || [],
    leader_agent: team.agent_ids?.[0] || "",
  };
}

function normalizeTask(task: LocalTask): Task {
  const status = (["backlog", "todo", "in_progress", "review", "done"].includes(task.status)
    ? task.status
    : task.status === "running"
      ? "in_progress"
      : "todo") as TaskStatus;
  return {
    id: String(task.id),
    number: task.id,
    identifier: `PY-${task.id}`,
    title: task.title,
    description: task.description || "",
    status,
    assignee: task.assignee || "",
    assigneeType: task.assignee ? "agent" : "",
    createdAt: toTimestamp(task.created_at),
    updatedAt: toTimestamp(task.updated_at),
  };
}

function parseRunResults(message: LocalQueueMessage): ResponseData[] {
  if (!message.result) return [];
  try {
    const result = JSON.parse(message.result) as {
      output?: string;
      runs?: { agent_id: string; output: string }[];
    };
    const runs = result.runs?.length ? result.runs : [{ agent_id: "orchestrator", output: result.output || "" }];
    return runs.map((run, index) => ({
      channel: "web",
      sender: message.sender,
      message: run.output,
      originalMessage: message.content,
      timestamp: toTimestamp(message.updated_at) + index,
      messageId: `${message.id}-${index}`,
      agent: run.agent_id,
    }));
  } catch {
    return [{
      channel: "web",
      sender: message.sender,
      message: message.result,
      originalMessage: message.content,
      timestamp: toTimestamp(message.updated_at),
      messageId: String(message.id),
      agent: "orchestrator",
    }];
  }
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
  const agents = await apiFetch<LocalAgent[]>("/api/agents");
  return Object.fromEntries(agents.map((agent) => [agent.id, normalizeAgent(agent)]));
}

export async function getTeams(): Promise<Record<string, TeamConfig>> {
  const teams = await apiFetch<LocalTeam[]>("/api/teams");
  return Object.fromEntries(teams.map((team) => [team.id, normalizeTeam(team)]));
}

export async function getSettings(): Promise<Settings> {
  const [agents, teams] = await Promise.all([getAgents(), getTeams()]);
  return {
    workspace: { name: "TinyAGI Python", path: ".tinyagi/workspace" },
    channels: { enabled: ["web"] },
    models: { provider: "local", openai: { model: "gpt-4o-mini" } },
    agents,
    teams,
    monitoring: { heartbeat_interval: 60 },
  };
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
  return { ok: true, settings: { ...(await getSettings()), ...settings } };
}

export async function runSetup(settings: Settings): Promise<{ ok: boolean; settings: Settings }> {
  return { ok: true, settings };
}

export async function applyServices(): Promise<{ ok: boolean; started: string[]; heartbeat: boolean; errors?: string[] }> {
  return { ok: true, started: ["web"], heartbeat: false };
}

export async function getQueueStatus(): Promise<QueueStatus> {
  const queue = await apiFetch<LocalQueueMessage[]>("/api/queue");
  return {
    incoming: queue.filter((item) => item.status === "queued").length,
    queued: queue.filter((item) => item.status === "queued").length,
    processing: queue.filter((item) => item.status === "running").length,
    outgoing: queue.filter((item) => item.status === "done").length,
    activeConversations: queue.filter((item) => item.status === "running" || item.status === "queued").length,
  };
}

export async function getProcessingMessages(): Promise<ProcessingMessage[]> {
  const queue = await apiFetch<LocalQueueMessage[]>("/api/queue?status=running");
  return queue.map((item) => ({
    id: item.id,
    messageId: String(item.id),
    channel: "web",
    sender: item.sender,
    message: item.content,
    agent: item.target,
    status: "processing",
    processAlive: true,
    startedAt: toTimestamp(item.updated_at),
    duration: Date.now() - toTimestamp(item.updated_at),
  }));
}

export async function killAgentSession(id: number): Promise<{ ok: boolean; agent: string; processKilled: boolean }> {
  return { ok: true, agent: String(id), processKilled: false };
}

export async function getResponses(limit = 20): Promise<ResponseData[]> {
  const queue = await apiFetch<LocalQueueMessage[]>(`/api/queue?status=done&limit=${limit}`);
  return queue.flatMap(parseRunResults).slice(0, limit);
}

export async function getLogs(limit = 100): Promise<{ lines: string[] }> {
  const events = await apiFetch<{ id: number; type: string; payload: Record<string, unknown>; created_at: string }[]>(`/api/events?limit=${limit}`);
  return {
    lines: events.map((event) => `${event.created_at} ${event.type} ${JSON.stringify(event.payload)}`),
  };
}

export async function saveAgent(
  id: string,
  agent: Partial<AgentConfig> & Pick<AgentConfig, "name" | "provider" | "model">
): Promise<{ ok: boolean; agent: AgentConfig }> {
  const saved = await apiFetch<LocalAgent>("/api/agents", {
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
  const saved = await apiFetch<LocalTeam>("/api/teams", {
    method: "POST",
    body: JSON.stringify({
      id,
      name: team.name,
      mode: "chain",
      agent_ids: team.agents,
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
  const agent = payload.agent || targetMatch?.[2] || "tinyagi";
  const target = targetMatch?.[1] ? `@team:${agent}` : `@agent:${agent}`;
  const message = await apiFetch<LocalQueueMessage>("/api/messages", {
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
  const queue = await apiFetch<LocalQueueMessage[]>(`/api/queue?limit=${limit}`);
  const messages: AgentMessage[] = [];
  queue.reverse().forEach((item) => {
    const timestamp = toTimestamp(item.created_at);
    if (item.id <= sinceId) return;
    if (item.target.endsWith(agentId) || item.result?.includes(`"agent_id":"${agentId}"`) || item.result?.includes(`"agent_id": "${agentId}"`)) {
      messages.push({
        id: item.id * 2,
        agent_id: agentId,
        role: "user",
        channel: "web",
        sender: item.sender,
        message_id: String(item.id),
        content: item.content,
        created_at: timestamp,
      });
      parseRunResults(item)
        .filter((run) => run.agent === agentId)
        .forEach((run, index) => {
          messages.push({
            id: item.id * 2 + index + 1,
            agent_id: agentId,
            role: "assistant",
            channel: "web",
            sender: agentId,
            message_id: run.messageId,
            content: run.message,
            created_at: run.timestamp,
          });
        });
    }
  });
  return messages.slice(-limit);
}

// ── Agent Workspace Data ──────────────────────────────────────────────────

export interface WorkspaceSkill {
  id: string;
  name: string;
  description: string;
}

export async function getAgentSkills(agentId: string): Promise<WorkspaceSkill[]> {
  return [];
}

export async function getAgentSystemPrompt(agentId: string): Promise<{ content: string; path: string }> {
  const agents = await apiFetch<LocalAgent[]>("/api/agents");
  const agent = agents.find((item) => item.id === agentId);
  return { content: agent?.system_prompt || agent?.role || "", path: agent?.workspace ? `${agent.workspace}/AGENTS.md` : "" };
}

export async function saveAgentSystemPrompt(agentId: string, content: string): Promise<{ ok: boolean }> {
  const local = await apiFetch<LocalAgent>(`/api/agents/${encodeURIComponent(agentId)}`);
  await apiFetch<LocalAgent>("/api/agents", {
    method: "POST",
    body: JSON.stringify({ ...local, system_prompt: content, workspace: local.workspace || null }),
  });
  return { ok: true };
}

export async function getAgentMemory(agentId: string): Promise<{ index: string; files: { name: string; path: string }[]; memoryDir: string }> {
  return { index: "Memory is not implemented in the Python adapter yet.", files: [], memoryDir: "" };
}

export async function getAgentHeartbeat(agentId: string): Promise<{ content: string; path: string; enabled: boolean; interval?: number }> {
  return { content: "", path: "", enabled: false };
}

export async function saveAgentHeartbeat(agentId: string, data: { content?: string; enabled?: boolean; interval?: number }): Promise<{ ok: boolean }> {
  return { ok: true };
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
  const tasks = await apiFetch<LocalTask[]>("/api/tasks");
  return tasks.map(normalizeTask);
}

export async function createTask(task: Partial<Task>): Promise<{ ok: boolean; task: Task }> {
  const saved = await apiFetch<LocalTask>("/api/tasks", {
    method: "POST",
    body: JSON.stringify({
      title: task.title || "Untitled task",
      description: task.description || "",
      status: task.status || "todo",
      assignee: task.assignee || null,
    }),
  });
  return { ok: true, task: normalizeTask(saved) };
}

export async function updateTask(id: string, task: Partial<Task>): Promise<{ ok: boolean; task: Task }> {
  const updated = await apiFetch<LocalTask>(`/api/tasks/${encodeURIComponent(id)}`, {
    method: "PUT",
    body: JSON.stringify({
      title: task.title,
      description: task.description,
      status: task.status,
      assignee: task.assignee,
    }),
  });
  return { ok: true, task: normalizeTask(updated) };
}

export async function deleteTask(id: string): Promise<{ ok: boolean }> {
  await apiFetch(`/api/tasks/${encodeURIComponent(id)}`, { method: "DELETE" });
  return { ok: true };
}

export async function getTask(id: string): Promise<Task & { commentCount: number }> {
  const task = await apiFetch<LocalTask>(`/api/tasks/${encodeURIComponent(id)}`);
  return { ...normalizeTask(task), commentCount: 0 };
}

export async function reorderTasks(columns: Record<string, string[]>): Promise<{ ok: boolean }> {
  return { ok: true };
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
  return [];
}

export async function createComment(
  taskId: string,
  data: { author: string; authorType: "user" | "agent"; content: string }
): Promise<{ ok: boolean; comment: Comment }> {
  return {
    ok: true,
    comment: {
      id: `${taskId}-${Date.now()}`,
      taskId,
      author: data.author,
      authorType: data.authorType,
      content: data.content,
      createdAt: Date.now(),
    },
  };
}

export async function deleteComment(id: string): Promise<{ ok: boolean }> {
  return { ok: true };
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
  const messages = await apiFetch<{ id: number; team_id: string; sender: string; message: string; created_at: string }[]>(
    `/api/chatroom/${encodeURIComponent(teamId)}?limit=${limit}&since=${sinceId}`,
  );
  return messages.map((message) => ({
    id: message.id,
    team_id: message.team_id,
    from_agent: message.sender,
    message: message.message,
    created_at: toTimestamp(message.created_at),
  }));
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
  return [];
}

export async function createProject(
  data: Pick<Project, "name" | "description">
): Promise<{ ok: boolean; project: Project }> {
  return {
    ok: true,
    project: {
      id: `project-${Date.now()}`,
      name: data.name,
      description: data.description,
      prefix: "PY",
      color: "#84cc16",
      status: "active",
      createdAt: Date.now(),
      updatedAt: Date.now(),
    },
  };
}

export async function updateProject(
  id: string,
  data: Partial<Omit<Project, "id" | "createdAt">>
): Promise<{ ok: boolean; project: Project }> {
  return {
    ok: true,
    project: {
      id,
      name: data.name || id,
      description: data.description || "",
      prefix: data.prefix || "PY",
      color: data.color || "#84cc16",
      status: data.status || "active",
      createdAt: Date.now(),
      updatedAt: Date.now(),
    },
  };
}

export async function deleteProject(id: string): Promise<{ ok: boolean }> {
  return { ok: true };
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
  return [];
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
  return {
    ok: true,
    schedule: {
      id: `schedule-${Date.now()}`,
      label: data.label || "Schedule",
      cron: data.cron || "",
      agentId: data.agentId,
      message: data.message,
      channel: data.channel || "web",
      sender: data.sender || "Web",
      enabled: true,
      createdAt: Date.now(),
      runAt: data.runAt,
    },
  };
}

export async function updateSchedule(
  id: string,
  data: Partial<Omit<Schedule, "id" | "createdAt">>
): Promise<{ ok: boolean; schedule: Schedule }> {
  return {
    ok: true,
    schedule: {
      id,
      label: data.label || "Schedule",
      cron: data.cron || "",
      agentId: data.agentId || "",
      message: data.message || "",
      channel: data.channel || "web",
      sender: data.sender || "Web",
      enabled: data.enabled ?? true,
      createdAt: Date.now(),
      runAt: data.runAt,
    },
  };
}

export async function deleteSchedule(id: string): Promise<{ ok: boolean }> {
  return { ok: true };
}

// ── Control Plane ─────────────────────────────────────────────────────────

export async function getSystemStatus(): Promise<{
  ok: boolean;
  uptime: number;
  server: { running: boolean; port: number };
  channels: Record<string, { running: boolean; pid?: number }>;
  heartbeat: { running: boolean; interval: number; lastSent: Record<string, number> };
}> {
  return {
    ok: true,
    uptime: 0,
    server: { running: true, port: 3777 },
    channels: { web: { running: true } },
    heartbeat: { running: false, interval: 60, lastSent: {} },
  };
}

export async function restartService(): Promise<{ ok: boolean; action: string }> {
  return { ok: true, action: "noop" };
}

export async function startChannel(channelId: string): Promise<{ ok: boolean }> {
  return { ok: true };
}

export async function stopChannel(channelId: string): Promise<{ ok: boolean }> {
  return { ok: true };
}

export async function restartChannel(channelId: string): Promise<{ ok: boolean }> {
  return { ok: true };
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
  return { pending: [], approved: [] };
}

export async function approvePairing(code: string): Promise<{ ok: boolean; entry?: PairingApproved }> {
  return { ok: true };
}

export async function revokePairing(channel: string, senderId: string): Promise<{ ok: boolean }> {
  return { ok: true };
}

export async function dismissPending(code: string): Promise<{ ok: boolean }> {
  return { ok: true };
}

// ── Custom Providers ──────────────────────────────────────────────────────

export interface CustomProvider {
  name: string;
  harness: "claude" | "codex";
  base_url: string;
  api_key: string;
  model?: string;
}

export async function getCustomProviders(): Promise<Record<string, CustomProvider>> {
  return {
    local: { name: "Local dry-run", harness: "codex", base_url: getApiBase(), api_key: "", model: "local" },
  };
}

export async function saveCustomProvider(id: string, provider: CustomProvider): Promise<{ ok: boolean }> {
  return { ok: true };
}

export async function deleteCustomProvider(id: string): Promise<{ ok: boolean }> {
  return { ok: true };
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
