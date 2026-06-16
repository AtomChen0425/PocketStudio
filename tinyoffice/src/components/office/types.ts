import type { PixelDeskStatus } from "./pixel-office-scene";
import type { AgentConfig, ResponseData, Task, TeamConfig } from "@/lib/api";

// ── Types ────────────────────────────────────────────────────────────────

export type LiveBubble = {
  id: string;
  agentId: string;
  message: string;
  timestamp: number;
  targetAgents: string[];
  messageId?: string;
  runId?: string;
  sessionId?: string;
};

export type TeamGroup = {
  id: string;
  label: string;
  memberIds: string[];
  color: string;
};

export type StationAssignment = {
  stationIndex: number;
  kind: "task" | "route";
  status: PixelDeskStatus;
  startAt: number;
  responseAt?: number;
  label: string;
  speaker?: boolean;
};

export type OverlayBubble = {
  id: string;
  x: number;
  y: number;
  color: string;
  heading: string;
  message: string;
};

export type ConversationEntry = {
  id: string;
  timestamp: number;
  role: "user" | "agent";
  agentId?: string;
  sender: string;
  message: string;
  targetAgents: string[];
  sourceOrder: number;
  messageId?: string;
  runId?: string;
  sessionId?: string;
  localStatus?: "sending" | "failed" | "dispatched" | "stored";
  dispatchStatus?: string | null;
  dispatchQueuedCount?: number | null;
  dispatchMessageIds?: number[];
};

export type AgentExecutionRunStatus = "running" | "completed" | "failed";

export type AgentExecutionRun = {
  key: string;
  agentId?: string;
  messageId?: string;
  runId?: string;
  sessionId?: string;
  status: AgentExecutionRunStatus;
  startedAt: number;
  updatedAt: number;
  completedAt?: number;
  summary: string;
  finalMessage?: string;
  finalMessageAt?: number;
  events: import("@/lib/api").OfficeEvent[];
};

export type AgentWorkSession = {
  rootMessageId: string;
  startedAt: number;
  completedAt?: number;
};

// ── Constants ────────────────────────────────────────────────────────────

export const AGENT_COLORS = ["#a3e635", "#84cc16", "#f59e0b", "#14b8a6", "#eab308", "#22c55e"];
export const AGENT_SESSION_RELEASE_MS = 6200;
export const OFFICE_STATION_COUNT = 8;
export const ARCHIVE_BUTTONS = [
  { id: "logs", label: "Logs" },
  { id: "runtime", label: "Runtime" },
  { id: "outgoing", label: "Ongoing Dock" },
  { id: "tasks", label: "Task Board" },
  { id: "routing", label: "Live Routing" },
] as const satisfies ReadonlyArray<{
  id: "logs" | "runtime" | "outgoing" | "tasks" | "routing";
  label: string;
}>;

// ── Utilities ────────────────────────────────────────────────────────────

export function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export function easeInOut(progress: number) {
  return progress * progress * (3 - 2 * progress);
}

export function lerp(from: number, to: number, progress: number) {
  return from + (to - from) * progress;
}

export function interpolatePoint(from: { x: number; y: number }, to: { x: number; y: number }, progress: number) {
  return {
    x: lerp(from.x, to.x, progress),
    y: lerp(from.y, to.y, progress),
  };
}

export function trimText(text: string, maxLength: number) {
  return text.length > maxLength ? `${text.slice(0, maxLength)}...` : text;
}

export function extractTargets(message: string) {
  const targets: string[] = [];
  const directTeam = message.match(/^@team:([a-zA-Z0-9_-]+)/);
  if (directTeam) targets.push(directTeam[1]);
  const directAgent = message.match(/^@(?!team:)(?:agent:)?([a-zA-Z0-9_-]+)/);
  if (directAgent && !targets.includes(directAgent[1])) targets.push(directAgent[1]);
  for (const match of message.matchAll(/\[@(\w[\w-]*?):/g)) {
    if (!targets.includes(match[1])) targets.push(match[1]);
  }
  return targets;
}

export function isErrorMessage(message: string) {
  return /\b(error|failed|failure|exception|timeout)\b/i.test(message);
}

export function taskTone(task: Task): PixelDeskStatus {
  if (task.status === "done") return "done";
  if (task.status === "review") return "pending";
  if (task.status === "in_progress") return "running";
  return "empty";
}

export function routeTone(message: string): PixelDeskStatus {
  return isErrorMessage(message) ? "error" : "running";
}

export function responseTone(response: ResponseData): PixelDeskStatus {
  return isErrorMessage(response.message) ? "error" : "done";
}

export function buildTeamGroups(
  agents: Record<string, AgentConfig> | null,
  teams: Record<string, TeamConfig> | null,
) {
  if (!agents) return [] as TeamGroup[];

  const allAgentIds = Object.keys(agents);
  const groupedIds = new Set<string>();
  const groups: TeamGroup[] = [];
  const teamEntries = teams ? Object.entries(teams) : [];

  teamEntries.forEach(([teamId, team], index) => {
    const members = team.agents.filter((memberId) => allAgentIds.includes(memberId));
    members.forEach((memberId) => groupedIds.add(memberId));
    if (members.length === 0) return;
    groups.push({
      id: teamId,
      label: team.name || teamId,
      memberIds: members,
      color: AGENT_COLORS[index % AGENT_COLORS.length],
    });
  });

  const independent = allAgentIds.filter((agentId) => !groupedIds.has(agentId));
  if (independent.length > 0) {
    groups.push({
      id: "independent",
      label: "Independent",
      memberIds: independent,
      color: AGENT_COLORS[groups.length % AGENT_COLORS.length],
    });
  }

  return groups;
}

export function responseSubtitle(response: ResponseData) {
  return response.agent ? `@${response.agent} -> ${response.channel}` : response.channel;
}

export function summarizeExecutionEvent(event: import("@/lib/api").OfficeEvent) {
  if (typeof event.summary === "string" && event.summary.trim()) return event.summary;
  if (typeof event.content === "string" && event.content.trim()) return event.content.slice(0, 180);
  if (typeof event.error === "string" && event.error.trim()) return event.error.slice(0, 180);
  if (typeof event.providerEventType === "string" && event.providerEventType.trim()) return event.providerEventType;
  if (typeof event.tool === "string" && event.tool.trim()) return `tool ${event.tool}`;
  return event.type;
}
