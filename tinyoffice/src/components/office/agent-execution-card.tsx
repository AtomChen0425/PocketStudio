"use client";

import { ChevronDown, ChevronRight, CircleDot, CheckCircle2, XCircle } from "lucide-react";
import type { OfficeEvent } from "@/lib/api";
import { timeAgo } from "@/lib/hooks";
import { summarizeExecutionEvent } from "./types";

type AgentExecutionCardProps = {
  agentId: string;
  agentName: string;
  events: OfficeEvent[];
  messageId?: string;
  runId?: string;
  sessionId?: string;
};

function matchesRun(
  event: OfficeEvent,
  anchor: { messageId?: string; runId?: string; sessionId?: string; agentId: string },
) {
  if (event.agentId !== anchor.agentId) return false;
  if (anchor.runId) return event.runId === anchor.runId;
  if (anchor.sessionId) return event.sessionId === anchor.sessionId;
  if (anchor.messageId) return event.messageId === anchor.messageId;
  return true;
}

function getRunStatus(events: OfficeEvent[]): "running" | "completed" | "failed" {
  if (events.some((event) => event.type === "message:failed")) return "failed";
  if (events.some((event) => event.type === "agent:response" || event.type === "message:done")) return "completed";
  return "running";
}

function getRunSummary(events: OfficeEvent[]): string {
  const reverse = [...events].sort((a, b) => b.timestamp - a.timestamp);
  for (const event of reverse) {
    const summary = summarizeExecutionEvent(event);
    if (summary.trim()) return summary;
  }
  return "Working...";
}

function getRunTitle(status: "running" | "completed" | "failed", count: number): string {
  if (status === "failed") return `failed · ${count} events`;
  if (status === "completed") return `completed · ${count} events`;
  return `running · ${count} events`;
}

export function AgentExecutionCard({
  agentId,
  agentName,
  events,
  messageId,
  runId,
  sessionId,
}: AgentExecutionCardProps) {
  const relevantEvents = events.filter((event) =>
    matchesRun(event, { agentId, messageId, runId, sessionId }),
  );

  if (relevantEvents.length === 0) return null;

  const sortedEvents = [...relevantEvents].sort((left, right) => left.timestamp - right.timestamp);
  const status = getRunStatus(sortedEvents);
  const summary = getRunSummary(sortedEvents);
  const startedAt = sortedEvents[0]?.timestamp ?? Date.now();
  const endedAt = sortedEvents[sortedEvents.length - 1]?.timestamp ?? startedAt;

  return (
    <details
      className="group rounded-none border border-[#885c47] bg-[#f4e7d6] px-3 py-2 text-[11px] text-[#241b16]"
      open={status === "running"}
    >
      <summary className="cursor-pointer list-none">
        <div className="flex items-start gap-2">
          <div className="mt-0.5 text-[#6f5c4b]">
            <ChevronRight className="size-3.5 group-open:hidden" />
            <ChevronDown className="hidden size-3.5 group-open:block" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
              <span className="font-semibold text-[#465e14]">{agentName}</span>
              <span className="text-[#6f5c4b]">{getRunTitle(status, sortedEvents.length)}</span>
            </div>
            <div className="mt-0.5 truncate text-[#6f5c4b]">{summary}</div>
          </div>
          <div className="shrink-0 text-right text-[#6f5c4b]">
            <div className="flex items-center justify-end gap-1">
              {status === "running" ? <CircleDot className="size-3.5 text-[#465e14]" /> : null}
              {status === "completed" ? <CheckCircle2 className="size-3.5 text-[#465e14]" /> : null}
              {status === "failed" ? <XCircle className="size-3.5 text-[#8b3e2f]" /> : null}
              <span>{timeAgo(endedAt)}</span>
            </div>
            <div className="mt-0.5">{timeAgo(startedAt)}</div>
          </div>
        </div>
      </summary>

      <div className="mt-2 space-y-2 border-t border-[#d2b892] pt-2">
        {sortedEvents.map((event) => (
          <div
            key={`${event.eventId ?? event.timestamp}-${event.type}`}
            className="rounded-none border border-[#d2b892] bg-[#fffaf1] px-2 py-1.5"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <div className="font-semibold text-[#465e14]">
                {event.type}
                {event.providerEventType ? <span className="ml-2 text-[#6f5c4b]">{event.providerEventType}</span> : null}
              </div>
              <div className="text-[#6f5c4b]">{timeAgo(event.timestamp)}</div>
            </div>
            <div className="mt-1 text-[#241b16]/90">{summarizeExecutionEvent(event)}</div>
            <details className="mt-1">
              <summary className="cursor-pointer text-[#6f5c4b] hover:text-[#241b16]">raw</summary>
              <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-words text-[10px] leading-5 text-[#6f5c4b]">
                {JSON.stringify(event, null, 2)}
              </pre>
            </details>
          </div>
        ))}
      </div>
    </details>
  );
}
