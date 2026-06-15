import type {
  AgentConfig,
  ChatMessage,
  ResponseData,
  Task,
  TaskStatus,
  TeamConfig,
} from "./api";

export type BackendAgent = {
  id: string;
  name: string;
  role: string;
  system_prompt?: string;
  provider: string;
  model?: string | null;
  model_provider?: string | null;
  api_key?: string | null;
  workspace?: string;
  heartbeat_enabled?: boolean;
  heartbeat_interval?: number | null;
};

export type BackendTeam = {
  id: string;
  name: string;
  mode: "chain" | "fanout" | "workflow";
  agent_ids: string[];
  leader_agent?: string;
  leaderAgent?: string;
  max_rounds?: number;
  maxRounds?: number;
  stop_when_idle?: boolean;
  stopWhenIdle?: boolean;
};

export type BackendQueueMessage = {
  id: number;
  target: string;
  content: string;
  sender: string;
  result?: string | null;
  created_at: string;
  updated_at: string;
};

export type BackendTask = {
  id: number;
  number?: number;
  identifier?: string;
  title: string;
  description: string;
  status: string;
  assignee?: string | null;
  assignee_type?: string;
  assigneeType?: "agent" | "team" | "";
  project_id?: string | null;
  projectId?: string | null;
  created_at: string;
  updated_at: string;
  createdAt?: number;
  updatedAt?: number;
  commentCount?: number;
};

export type BackendChatMessage = {
  id: number;
  team_id: string;
  from_agent?: string;
  sender?: string;
  message: string;
  created_at: string;
};

export type BackendResponseData = ResponseData & {
  id?: number;
  senderId?: string | null;
  metadata?: Record<string, unknown>;
  status?: string;
  ackedAt?: number | null;
};

export function toTimestamp(value?: string | number | null): number {
  if (typeof value === "number") return value;
  if (!value) return Date.now();
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : Date.now();
}

export function normalizeAgent(agent: BackendAgent): AgentConfig {
  return {
    name: agent.name,
    provider: agent.provider || "local",
    model: agent.model || "",
    model_provider: agent.model_provider || "",
    api_key: agent.api_key || "",
    working_directory: agent.workspace || "",
    system_prompt: agent.system_prompt || agent.role || "",
    heartbeat: {
      enabled: agent.heartbeat_enabled ?? true,
      interval: agent.heartbeat_interval ?? undefined,
    },
  };
}

export function normalizeTeam(team: BackendTeam): TeamConfig {
  return {
    name: team.name,
    agents: team.agent_ids || [],
    leader_agent: team.leader_agent || team.leaderAgent || team.agent_ids?.[0] || "",
    mode: team.mode || "chain",
    max_rounds: team.max_rounds ?? team.maxRounds ?? 1,
  };
}

export function normalizeTask(task: BackendTask): Task {
  const status = (["backlog", "todo", "in_progress", "review", "done"].includes(task.status)
    ? task.status
    : task.status === "running"
      ? "in_progress"
      : "todo") as TaskStatus;
  const assigneeType = task.assignee_type || task.assigneeType || "";
  const projectId = task.project_id || task.projectId || undefined;
  return {
    id: String(task.id),
    number: task.number || task.id,
    identifier: task.identifier || `T-${task.number || task.id}`,
    title: task.title,
    description: task.description || "",
    status,
    assignee: task.assignee || "",
    assigneeType: assigneeType === "team" ? "team" : assigneeType === "agent" || task.assignee ? "agent" : "",
    projectId,
    createdAt: toTimestamp(task.createdAt || task.created_at),
    updatedAt: toTimestamp(task.updatedAt || task.updated_at),
  };
}

export function normalizeChatMessage(message: BackendChatMessage): ChatMessage {
  return {
    id: message.id,
    team_id: message.team_id,
    from_agent: message.from_agent || message.sender || "unknown",
    message: message.message,
    created_at: toTimestamp(message.created_at),
  };
}
