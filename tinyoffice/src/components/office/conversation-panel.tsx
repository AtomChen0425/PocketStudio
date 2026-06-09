"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowUp, Square } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  PromptInput,
  PromptInputAction,
  PromptInputActions,
  PromptInputTextarea,
} from "@/components/ui/prompt-input";
import { Markdown } from "@/components/ui/markdown";
import { PIXEL_SCENE_LAYOUT } from "./pixel-office-scene";
import { isInternalAgentInput, sendMessage, type AgentConfig, type AgentMessage, type OfficeEvent, type TeamConfig } from "@/lib/api";
import { timeAgo } from "@/lib/hooks";
import { AgentExecutionCard } from "./agent-execution-card";
import type { AgentExecutionRun, ConversationEntry, LiveBubble } from "./types";

const AGENT_COLORS = [
  "bg-blue-500", "bg-emerald-500", "bg-purple-500", "bg-orange-500",
  "bg-pink-500", "bg-cyan-500", "bg-yellow-500", "bg-red-500",
];

function agentColor(agentId: string): string {
  let hash = 0;
  for (let i = 0; i < agentId.length; i++) {
    hash = ((hash << 5) - hash + agentId.charCodeAt(i)) | 0;
  }
  return AGENT_COLORS[Math.abs(hash) % AGENT_COLORS.length];
}

type ConversationPanelProps = {
  agents: Record<string, AgentConfig> | null;
  teams: Record<string, TeamConfig> | null;
  agentEntries: [string, AgentConfig][];
  agentHistories: Record<string, AgentMessage[]> | null;
  bubbles: LiveBubble[];
  runtimeEvents: OfficeEvent[];
  selectedAgentId?: string | null;
};

export function ConversationPanel({
  agents,
  teams,
  agentEntries,
  agentHistories,
  bubbles,
  runtimeEvents,
  selectedAgentId,
}: ConversationPanelProps) {
  const [chatInput, setChatInput] = useState("");
  const [sending, setSending] = useState(false);
  const [conversationFilter, setConversationFilter] = useState<string>("all");

  const conversationScrollRef = useRef<HTMLDivElement | null>(null);
  const conversationStickToBottomRef = useRef(true);

  const setConversationFilterAndStick = useCallback((nextFilter: string) => {
    conversationStickToBottomRef.current = true;
    setConversationFilter(nextFilter);
  }, []);

  // Sync external agent selection to conversation filter
  useEffect(() => {
    if (selectedAgentId) {
      setConversationFilterAndStick(selectedAgentId);
    }
  }, [selectedAgentId, setConversationFilterAndStick]);

  const handleSend = useCallback(async () => {
    if (!chatInput.trim() || sending) return;
    setSending(true);
    try {
      const target =
        conversationFilter.startsWith("team:")
          ? `@${conversationFilter}`
          : conversationFilter !== "all"
            ? `@${conversationFilter}`
            : "";
      const message = target && !chatInput.trim().startsWith("@") ? `${target} ${chatInput.trim()}` : chatInput.trim();

      await sendMessage({ message, sender: "Web", channel: "web" });
      setChatInput("");
    } catch {
      // send errors are transient; the message will appear via SSE if it went through
    } finally {
      setSending(false);
    }
  }, [chatInput, conversationFilter, sending]);

  const conversationEntries = useMemo<ConversationEntry[]>(() => {
    const historyEntries: ConversationEntry[] = [];
    const seenHistory = new Set<string>();

    Object.entries(agentHistories ?? {}).forEach(([agentId, messages]) => {
      messages.forEach((message, index) => {
        if (isInternalAgentInput(message)) return;
        const dedupeKey =
          message.role === "user"
            ? `user:${message.message_id || message.id}:${message.content}`
            : `agent:${agentId}:${message.message_id || message.id}:${message.content}`;
        if (seenHistory.has(dedupeKey)) return;
        seenHistory.add(dedupeKey);

        historyEntries.push({
          id: `history-${agentId}-${message.id}`,
          timestamp: message.created_at,
          role: message.role === "user" ? "user" : "agent",
          agentId: message.role === "assistant" ? agentId : undefined,
          sender: message.role === "user" ? "You" : agents?.[agentId]?.name || `@${agentId}`,
          message: message.content,
          targetAgents: message.role === "user" ? [agentId] : [],
          sourceOrder: index,
          messageId: message.message_id,
        });
      });
    });

    const liveEntries = [...bubbles].map((bubble, index) => {
      if (bubble.agentId.startsWith("_user_")) {
        return {
          id: bubble.id,
          timestamp: bubble.timestamp,
          role: "user" as const,
          sender: "You",
          message: bubble.message,
          targetAgents: bubble.targetAgents,
          sourceOrder: index,
          messageId: bubble.messageId,
          runId: bubble.runId,
          sessionId: bubble.sessionId,
        };
      }

      const agent = agents?.[bubble.agentId];
      return {
        id: bubble.id,
        timestamp: bubble.timestamp,
        role: "agent" as const,
        agentId: bubble.agentId,
        sender: agent?.name || `@${bubble.agentId}`,
        message: bubble.message,
        targetAgents: bubble.targetAgents,
        sourceOrder: index,
        messageId: bubble.messageId,
        runId: bubble.runId,
        sessionId: bubble.sessionId,
      };
    });

    const merged = [...historyEntries, ...liveEntries];
    const seen = new Set<string>();
    return merged
      .sort((left, right) => {
        if (left.timestamp !== right.timestamp) return left.timestamp - right.timestamp;
        if (left.role !== right.role) return left.role === "user" ? -1 : 1;
        return left.sourceOrder - right.sourceOrder;
      })
      .filter((entry) => {
        // Use time-bucket (5s window) to deduplicate messages that arrive via
        // both SSE (live bubbles) and API polling (agent histories) with
        // slightly different timestamps.
        const key = entry.role === "user"
          ? entry.messageId
            ? `user:${entry.messageId}`
            : `user:${entry.agentId || "boss"}:${Math.round(entry.timestamp / 5000)}:${entry.message}`
          : `${entry.role}:${entry.agentId || "boss"}:${entry.messageId || "no-message"}:${entry.message}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
  }, [agentHistories, agents, bubbles]);

  const executionRuns = useMemo<AgentExecutionRun[]>(() => {
    const runs = new Map<string, AgentExecutionRun>();

    runtimeEvents.forEach((event) => {
      if (!event.messageId || !event.agentId) return;
      const runKey = event.runId || event.sessionId || `message:${event.messageId}`;
      const key = `${event.messageId}:${event.agentId}:${runKey}`;
      let run = runs.get(key);
      if (!run) {
        run = {
          key,
          agentId: event.agentId,
          messageId: event.messageId,
          runId: event.runId,
          sessionId: event.sessionId,
          status: "running",
          startedAt: event.timestamp,
          updatedAt: event.timestamp,
          summary: "",
          events: [],
        };
        runs.set(key, run);
      }
      run.events.push(event);
      run.updatedAt = Math.max(run.updatedAt, event.timestamp);
      run.startedAt = Math.min(run.startedAt, event.timestamp);
      if (event.type === "message:failed") {
        run.status = "failed";
      } else if (event.type === "agent:response" || event.type === "message:done") {
        if (run.status !== "failed") run.status = "completed";
      }
    });

    return [...runs.values()].sort((left, right) => {
      if (left.startedAt !== right.startedAt) return left.startedAt - right.startedAt;
      const leftAgentId = left.agentId ?? "";
      const rightAgentId = right.agentId ?? "";
      if (leftAgentId !== rightAgentId) return leftAgentId.localeCompare(rightAgentId);
      return left.key.localeCompare(right.key);
    });
  }, [runtimeEvents]);

  const visibleConversation = useMemo(() => {
    if (conversationFilter === "all") return conversationEntries.slice(-60);
    if (conversationFilter.startsWith("team:")) {
      const teamId = conversationFilter.slice("team:".length);
      const memberIds = teams?.[teamId]?.agents ?? [];
      return conversationEntries
        .filter((entry) => {
          if (entry.targetAgents.includes(teamId)) return true;
          if (entry.agentId && memberIds.includes(entry.agentId)) return true;
          return entry.targetAgents.some((target) => memberIds.includes(target));
        })
        .slice(-60);
    }
    return conversationEntries
      .filter((entry) => {
        if (entry.role === "agent") return entry.agentId === conversationFilter;
        return entry.targetAgents.includes(conversationFilter);
      })
      .slice(-60);
  }, [conversationEntries, conversationFilter, teams]);

  const visibleExecutionRuns = useMemo(() => {
    const teamId = conversationFilter.startsWith("team:") ? conversationFilter.slice("team:".length) : "";
    const memberIds = teamId ? teams?.[teamId]?.agents ?? [] : [];
    return executionRuns.filter((run) => {
      const runAgentId = run.agentId ?? "";
      if (conversationFilter === "all") return true;
      if (conversationFilter.startsWith("team:")) {
        return memberIds.includes(runAgentId);
      }
      return runAgentId === conversationFilter;
    });
  }, [conversationFilter, executionRuns, teams]);

  const visibleTimeline = useMemo(() => {
    const items = [
      ...visibleConversation.map((entry, index) => ({
        kind: "message" as const,
        id: entry.id,
        timestamp: entry.timestamp,
        sourceOrder: index,
        entry,
      })),
      ...visibleExecutionRuns.map((run, index) => ({
        kind: "run" as const,
        id: `run:${run.key}`,
        timestamp: run.startedAt,
        sourceOrder: 10_000 + index,
        run,
      })),
    ];

    return items.sort((left, right) => {
      if (left.timestamp !== right.timestamp) return left.timestamp - right.timestamp;
      if (left.kind !== right.kind) return left.kind === "message" ? -1 : 1;
      return left.sourceOrder - right.sourceOrder;
    });
  }, [visibleConversation, visibleExecutionRuns]);

  useEffect(() => {
    const node = conversationScrollRef.current;
    if (!node) return;
    if (!conversationStickToBottomRef.current) return;
    node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
  }, [visibleConversation]);

  const handleConversationScroll = useCallback(() => {
    const node = conversationScrollRef.current;
    if (!node) return;
    const distanceFromBottom = node.scrollHeight - node.scrollTop - node.clientHeight;
    conversationStickToBottomRef.current = distanceFromBottom <= 32;
  }, []);

  const activeButtonClass = "border-[#465e14] bg-[#111111] text-[#a3e635]";
  const inactiveButtonClass = "border-[#885c47] bg-[#dcc3a3] text-[#5c4637] hover:border-[#465e14] hover:bg-[#111111] hover:text-[#a3e635]";
  const teamEntries = Object.entries(teams ?? {});
  const hasTeams = teamEntries.length > 0;

  return (
    <div
      className="absolute right-0 top-0 z-40 flex flex-col overflow-hidden border-l border-[#885c47] bg-[#b38857] shadow-[-18px_0_36px_rgba(36,24,16,0.2)]"
      style={{
        width: `${(584 / PIXEL_SCENE_LAYOUT.width) * 100}%`,
        height: "100%",
      }}
      >
      <div className="border-b border-[#885c47] bg-[#be9565] px-4 py-3 shadow-[0_1px_0_rgba(255,255,255,0.08)_inset]">
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setConversationFilterAndStick("all")}
            className={`border px-3 py-1.5 font-mono text-[10px] transition ${
              conversationFilter === "all" ? activeButtonClass : inactiveButtonClass
            }`}
          >
            All Agents
          </button>
          {hasTeams && teamEntries.map(([teamId, team]) => (
            <button
              key={`team:${teamId}`}
              type="button"
              onClick={() => setConversationFilterAndStick(`team:${teamId}`)}
              className={`border px-3 py-1.5 font-mono text-[10px] transition ${
                conversationFilter === `team:${teamId}` ? activeButtonClass : inactiveButtonClass
              }`}
            >
              {team.name || `@team:${teamId}`}
            </button>
          ))}
          {hasTeams ? (
            <Select
              value={
                conversationFilter.startsWith("team:") || conversationFilter === "all"
                  ? ""
                  : conversationFilter
              }
              onValueChange={(value) => setConversationFilterAndStick(value)}
            >
              <SelectTrigger
                className={`h-auto min-h-[32px] border px-3 py-1.5 font-mono text-[10px] shadow-none ${
                  conversationFilter.startsWith("team:") || conversationFilter === "all"
                    ? "border-[#885c47] bg-[#dcc3a3] text-[#5c4637] hover:border-[#465e14] hover:bg-[#111111] hover:text-[#a3e635]"
                    : "border-[#465e14] bg-[#111111] text-[#a3e635]"
                }`}
              >
                <SelectValue placeholder="Agents" />
              </SelectTrigger>
              <SelectContent className="border-[#885c47] bg-[#f4e7d6] text-[#241b16] shadow-[0_10px_24px_rgba(36,24,16,0.22)]">
                {agentEntries.map(([agentId, agent]) => (
                  <SelectItem
                    key={agentId}
                    value={agentId}
                    className="text-[#241b16] data-[highlighted]:bg-[#be9565] data-[highlighted]:text-[#241b16] data-[state=checked]:bg-[#d4c4a8] data-[state=checked]:text-[#241b16]"
                  >
                    {agent.name || `@${agentId}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            agentEntries.map(([agentId, agent]) => (
              <button
                key={agentId}
                type="button"
                onClick={() => setConversationFilterAndStick(agentId)}
                className={`border px-3 py-1.5 font-mono text-[10px] transition ${
                  conversationFilter === agentId ? activeButtonClass : inactiveButtonClass
                }`}
              >
                {agent.name || `@${agentId}`}
              </button>
            ))
          )}
        </div>
      </div>

      <div
        ref={conversationScrollRef}
        onScroll={handleConversationScroll}
        className="min-h-0 flex-1 overflow-y-auto border-y border-[#885c47] bg-[#ead8c3] px-4 py-4"
      >
        <div className="space-y-3">
          {visibleTimeline.length > 0 ? (
            visibleTimeline.map((item) => {
              if (item.kind === "run") {
                const agentId = item.run.agentId ?? "";
                const agentName = agents?.[agentId]?.name || `@${agentId}`;
                const initials = agentName.slice(0, 2).toUpperCase();
                return (
                  <div key={item.id} className="flex items-start gap-3">
                    <div className={`flex h-8 w-8 items-center justify-center text-[10px] font-bold uppercase shrink-0 text-white ${agentColor(agentId)}`}>
                      {initials}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline gap-2">
                        <span className="text-sm font-semibold text-[#241b16]">{agentName}</span>
                        <span className="text-[10px] text-[#6f5c4b]">
                          {timeAgo(item.run.startedAt)}
                        </span>
                      </div>
                      <div className="mt-1">
                        <AgentExecutionCard
                          key={item.run.key}
                          agentId={agentId}
                          agentName={agentName}
                          events={item.run.events}
                          messageId={item.run.messageId}
                          runId={item.run.runId}
                          sessionId={item.run.sessionId}
                        />
                      </div>
                    </div>
                  </div>
                );
              }

              const entry = item.entry;
              const isUser = entry.role === "user";
              const initials = entry.sender.slice(0, 2).toUpperCase();
              return (
                <div key={item.id} className="flex items-start gap-3">
                  <div
                    className={`flex h-8 w-8 items-center justify-center text-[10px] font-bold uppercase shrink-0 text-white ${
                      isUser ? "bg-[#465e14]" : agentColor(entry.agentId ?? "")
                    }`}
                  >
                    {isUser ? "You" : initials}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline gap-2">
                      <span className="text-sm font-semibold text-[#241b16]">{entry.sender}</span>
                      <span className="text-[10px] text-[#6f5c4b]">
                        {timeAgo(entry.timestamp)}
                      </span>
                    </div>
                    <Markdown className="prose prose-sm mt-0.5 max-w-none break-words text-[#241b16]/90 [&_span.rounded-sm]:bg-[#d4c4a8] [&_span.rounded-sm]:text-[#5c4637]">
                      {entry.message}
                    </Markdown>
                  </div>
                </div>
              );
            })
          ) : (
            <div className="border border-dashed border-[#885c47] bg-[#f4e7d6] px-4 py-6 text-center text-sm text-[#6f5c4b]">
              No messages for this view
            </div>
          )}
        </div>
      </div>

      <div className="border-t border-[#885c47] bg-[#be9565] px-4 py-3 shadow-[0_-1px_0_rgba(255,255,255,0.08)_inset]">
        <PromptInput
          value={chatInput}
          onValueChange={setChatInput}
          isLoading={sending}
          onSubmit={handleSend}
          className="relative w-full rounded-none border-[#885c47] bg-[#f4e7d6] shadow-none"
        >
          <PromptInputTextarea
            placeholder={
              conversationFilter === "all"
                ? "Message @agent or @team..."
                : conversationFilter.startsWith("team:")
                  ? `Message @${conversationFilter}...`
                  : `Message @${conversationFilter}...`
            }
            className="min-h-[70px] text-[#241b16] placeholder:text-[#6f5c4b]"
          />
          <PromptInputActions className="absolute bottom-2 right-2">
            <PromptInputAction
              tooltip={sending ? "Sending..." : "Send message"}
            >
              <Button
                variant="default"
                size="icon"
                className="h-8 w-8 rounded-full border-[#465e14] bg-[#161812] text-[#a3e635] hover:bg-[#465e14] hover:text-[#d9f99d]"
                disabled={!chatInput.trim() || sending}
                onClick={handleSend}
              >
                {sending ? (
                  <Square className="size-5 fill-current" />
                ) : (
                  <ArrowUp className="size-5" />
                )}
              </Button>
            </PromptInputAction>
          </PromptInputActions>
        </PromptInput>
      </div>
    </div>
  );
}
