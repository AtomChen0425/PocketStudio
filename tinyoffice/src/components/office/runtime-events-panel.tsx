"use client";

import { useMemo } from "react";
import type { AgentConfig, OfficeEvent } from "@/lib/api";
import { timeAgo } from "@/lib/hooks";

type RuntimeEventsPanelProps = {
  events: OfficeEvent[];
  agentEntries: [string, AgentConfig][];
};

type RuntimeGroup = {
  id: string;
  title: string;
  subtitle: string;
  timestamp: number;
  events: OfficeEvent[];
};

function safeStringify(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function resolveAgentName(agentEntries: [string, AgentConfig][], agentId?: string): string {
  if (!agentId) return "system";
  return agentEntries.find(([id]) => id === agentId)?.[1].name || `@${agentId}`;
}

function summarizeEvent(event: OfficeEvent): string {
  if (typeof event.summary === "string" && event.summary.trim()) return event.summary;
  if (typeof event.content === "string" && event.content.trim()) return event.content.slice(0, 220);
  if (typeof event.message === "string" && event.message.trim()) return event.message.slice(0, 220);
  if (typeof event.error === "string" && event.error.trim()) return event.error.slice(0, 220);
  if (event.process && typeof event.process === "object") return "process metadata";
  if (event.raw && typeof event.raw === "object") return "raw provider event";
  return event.type;
}

function eventGroupKey(event: OfficeEvent): string {
  if (event.messageId != null && event.messageId !== "") return `message:${event.messageId}`;
  if (event.responseId != null) return `response:${event.responseId}`;
  if (event.agentId) return `agent:${event.agentId}:${event.eventId ?? event.timestamp}`;
  return `event:${event.eventId ?? event.timestamp}`;
}

function eventGroupTitle(group: RuntimeGroup): string {
  if (group.id.startsWith("message:")) return `Message ${group.id.slice("message:".length)}`;
  if (group.id.startsWith("response:")) return `Response ${group.id.slice("response:".length)}`;
  if (group.id.startsWith("agent:")) return group.events[0]?.agentId ? `@${group.events[0].agentId}` : "Agent run";
  return "System event";
}

export function RuntimeEventsPanel({ events, agentEntries }: RuntimeEventsPanelProps) {
  const groups = useMemo(() => {
    const grouped = new Map<string, RuntimeGroup>();
    events.forEach((event) => {
      const key = eventGroupKey(event);
      const current = grouped.get(key);
      const title = event.messageId
        ? `Message ${event.messageId}`
        : event.agentId
          ? resolveAgentName(agentEntries, event.agentId)
          : event.type;
      const subtitle = event.agentId
        ? `${event.type} · ${resolveAgentName(agentEntries, event.agentId)}`
        : event.messageId
          ? `${event.type} · message ${event.messageId}`
          : event.type;
      if (!current) {
        grouped.set(key, {
          id: key,
          title,
          subtitle,
          timestamp: event.timestamp,
          events: [event],
        });
        return;
      }
      current.events.push(event);
      current.timestamp = Math.max(current.timestamp, event.timestamp);
      current.subtitle = subtitle;
      current.title = title;
    });
    return [...grouped.values()]
      .sort((a, b) => a.timestamp - b.timestamp)
      .slice(-24);
  }, [agentEntries, events]);

  const totals = useMemo(() => {
    const agentIds = new Set<string>();
    const messageIds = new Set<string>();
    events.forEach((event) => {
      if (event.agentId) agentIds.add(event.agentId);
      if (event.messageId) messageIds.add(event.messageId);
    });
    return {
      events: events.length,
      groups: groups.length,
      agents: agentIds.size,
      messages: messageIds.size,
    };
  }, [events, groups.length]);

  return (
    <div className="space-y-3 font-mono text-xs text-stone-300">
      <div className="grid grid-cols-2 gap-2">
        <div className="border border-stone-800 bg-stone-900/90 px-3 py-2">
          <div className="text-stone-500">events</div>
          <div className="mt-1 text-lime-300">{totals.events}</div>
        </div>
        <div className="border border-stone-800 bg-stone-900/90 px-3 py-2">
          <div className="text-stone-500">runs</div>
          <div className="mt-1 text-lime-300">{totals.groups}</div>
        </div>
        <div className="border border-stone-800 bg-stone-900/90 px-3 py-2">
          <div className="text-stone-500">agents</div>
          <div className="mt-1 text-lime-300">{totals.agents}</div>
        </div>
        <div className="border border-stone-800 bg-stone-900/90 px-3 py-2">
          <div className="text-stone-500">messages</div>
          <div className="mt-1 text-lime-300">{totals.messages}</div>
        </div>
      </div>

      {groups.length > 0 ? (
        groups.map((group, groupIndex) => (
          <details
            key={group.id}
            className="border border-stone-800 bg-stone-900/90"
            open={groupIndex === groups.length - 1}
          >
            <summary className="cursor-pointer list-none px-3 py-2">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-lime-300">{eventGroupTitle(group)}</div>
                  <div className="mt-0.5 truncate text-stone-500">{group.subtitle}</div>
                </div>
                <div className="shrink-0 text-right text-stone-500">
                  <div>{timeAgo(group.timestamp)}</div>
                  <div>{group.events.length} events</div>
                </div>
              </div>
            </summary>
            <div className="border-t border-stone-800 px-3 py-2">
              <div className="space-y-2">
                {group.events.map((event) => (
                  <div key={`${event.eventId ?? event.timestamp}-${event.type}`} className="border border-stone-800 bg-stone-950/70 px-3 py-2">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <div className="text-lime-300">
                        {event.type}
                        {event.agentId ? <span className="ml-2 text-stone-500">@{event.agentId}</span> : null}
                      </div>
                      <div className="text-stone-500">{timeAgo(event.timestamp)}</div>
                    </div>
                    <div className="mt-1 text-stone-300">
                      {summarizeEvent(event)}
                    </div>
                    <details className="mt-2">
                      <summary className="cursor-pointer text-stone-500 hover:text-stone-300">raw</summary>
                      <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words text-[11px] leading-5 text-stone-400">
                        {safeStringify(event)}
                      </pre>
                    </details>
                  </div>
                ))}
              </div>
            </div>
          </details>
        ))
      ) : (
        <div className="border border-stone-800 bg-stone-900/90 px-3 py-2 text-stone-500">No runtime events yet</div>
      )}
    </div>
  );
}
