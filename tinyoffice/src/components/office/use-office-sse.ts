"use client";

import { useEffect, useRef, useState } from "react";
import { subscribeToEvents, type EventData, type OfficeEvent } from "@/lib/api";
import {
  AGENT_SESSION_RELEASE_MS,
  OFFICE_BUBBLE_RETENTION_MS,
  extractTargets,
  type AgentWorkSession,
  type LiveBubble,
} from "./types";

export function useOfficeSse() {
  const [bubbles, setBubbles] = useState<LiveBubble[]>([]);
  const [runtimeEvents, setRuntimeEvents] = useState<OfficeEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [clock, setClock] = useState({ now: Date.now(), frame: 0 });
  const [agentWorkSessions, setAgentWorkSessions] = useState<Record<string, AgentWorkSession>>({});

  const seenRef = useRef(new Set<string>());
  const rootSessionsRef = useRef(new Map<string, { startedAt: number; agentIds: Set<string>; completedAt?: number }>());
  const openRootOrderRef = useRef<string[]>([]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setClock((current) => ({ now: Date.now(), frame: current.frame + 1 }));
    }, 120);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    setAgentWorkSessions((current) => {
      let changed = false;
      const next: Record<string, AgentWorkSession> = {};
      Object.entries(current).forEach(([agentId, session]) => {
        if (session.completedAt && Date.now() - session.completedAt > AGENT_SESSION_RELEASE_MS) {
          changed = true;
          return;
        }
        next[agentId] = session;
      });
      return changed ? next : current;
    });
  }, [clock.now]);

  useEffect(() => {
    const latestOpenRootId = () => {
      for (let index = openRootOrderRef.current.length - 1; index >= 0; index -= 1) {
        const messageId = openRootOrderRef.current[index];
        const session = rootSessionsRef.current.get(messageId);
        if (session && !session.completedAt) return messageId;
      }
      return null;
    };

    const attachAgentToLatestRoot = (agentId: string, timestamp: number) => {
      const rootMessageId = latestOpenRootId();
      if (!rootMessageId) return;

      const rootSession = rootSessionsRef.current.get(rootMessageId);
      if (!rootSession) return;

      rootSession.agentIds.add(agentId);
      setAgentWorkSessions((current) => {
        const existing = current[agentId];
        if (existing && existing.rootMessageId === rootMessageId && !existing.completedAt) {
          return current;
        }
        return {
          ...current,
          [agentId]: {
            rootMessageId,
            startedAt: existing && !existing.completedAt ? existing.startedAt : timestamp,
          },
        };
      });
    };

    const appendRuntimeEvent = (event: EventData, messageId?: string) => {
      const payload = event as Record<string, unknown>;
      const normalized: OfficeEvent = {
        ...payload,
        type: event.type,
        timestamp: event.timestamp,
        eventId: typeof payload.eventId === "number" ? payload.eventId : undefined,
        messageId:
          messageId ||
          (typeof payload.messageId === "string" ? payload.messageId : undefined) ||
          (typeof payload.message_id === "string" ? payload.message_id : undefined),
        agentId: typeof payload.agentId === "string" ? payload.agentId : undefined,
        runId: typeof payload.runId === "string" ? payload.runId : undefined,
        sessionId: typeof payload.sessionId === "string" ? payload.sessionId : undefined,
      };

      setRuntimeEvents((current) => {
        const fingerprint = `${normalized.eventId ?? ""}:${normalized.type}:${normalized.timestamp}:${normalized.messageId ?? ""}:${normalized.agentId ?? ""}:${normalized.runId ?? ""}:${normalized.sessionId ?? ""}`;
        if (
          current.some(
            (entry) =>
              `${entry.eventId ?? ""}:${entry.type}:${entry.timestamp}:${entry.messageId ?? ""}:${entry.agentId ?? ""}:${entry.runId ?? ""}:${entry.sessionId ?? ""}` ===
              fingerprint,
          )
        ) {
          return current;
        }
        const next = [...current, normalized];
        return next.length > 200 ? next.slice(-200) : next;
      });
    };

    const unsubscribe = subscribeToEvents(
      (event: EventData) => {
        setConnected(true);
        const fingerprint = `${event.type}:${event.timestamp}:${(event as Record<string, unknown>).messageId ?? ""}:${(event as Record<string, unknown>).agentId ?? ""}`;
        if (seenRef.current.has(fingerprint)) return;
        seenRef.current.add(fingerprint);
        if (seenRef.current.size > 500) {
          const entries = [...seenRef.current];
          seenRef.current = new Set(entries.slice(entries.length - 300));
        }

        const payload = event as Record<string, unknown>;
        const agentId = payload.agentId ? String(payload.agentId) : undefined;

        if (event.type === "message:incoming") {
          const message = (payload.message as string) || "";
          const sender = (payload.sender as string) || "User";
          const messageId = payload.messageId ? String(payload.messageId) : undefined;
          const target = payload.target ? String(payload.target) : "";
          if (!message) return;
          appendRuntimeEvent(event, messageId);

          if (messageId) {
            rootSessionsRef.current.set(messageId, {
              startedAt: event.timestamp,
              agentIds: new Set<string>(),
            });
            openRootOrderRef.current = [...openRootOrderRef.current.filter((id) => id !== messageId), messageId];
          }

        setBubbles((current) =>
            [
              ...current,
              {
                id: `${event.timestamp}-${Math.random().toString(36).slice(2, 7)}`,
                agentId: `_user_${sender}`,
                message,
                timestamp: event.timestamp,
                targetAgents: target ? extractTargets(target) : extractTargets(message),
                messageId,
              },
            ].slice(-200),
          );
        }

        if (event.type === "message:processing" || event.type === "message:failed" || event.type === "message:done") {
          appendRuntimeEvent(event, payload.messageId ? String(payload.messageId) : undefined);
        }

        if (event.type === "response:queued" || event.type === "chat:posted" || event.type === "team:chatroom") {
          appendRuntimeEvent(event, payload.messageId ? String(payload.messageId) : undefined);
        }

        if (
          event.type === "agent:invoke" ||
          event.type === "agent:progress" ||
          event.type === "agent:stdout" ||
          event.type === "agent:stderr" ||
          event.type === "agent:tool_call" ||
          event.type === "agent:tool_result"
        ) {
          appendRuntimeEvent(
            event,
            payload.messageId ? String(payload.messageId) : payload.sessionId ? String(payload.sessionId) : latestOpenRootId() || undefined,
          );
          if (agentId) attachAgentToLatestRoot(agentId, event.timestamp);
        }

        if (event.type === "agent:invoke" && agentId) {
          attachAgentToLatestRoot(agentId, event.timestamp);
        }

        if (event.type === "agent:mention") {
          const toAgent = payload.toAgent ? String(payload.toAgent) : undefined;
          const fromAgent = payload.fromAgent ? String(payload.fromAgent) : undefined;
          appendRuntimeEvent(event, latestOpenRootId() || undefined);
          if (fromAgent) attachAgentToLatestRoot(fromAgent, event.timestamp);
          if (toAgent) attachAgentToLatestRoot(toAgent, event.timestamp);
        }

        if (event.type === "agent:response" && agentId) {
          const responseMessageId = payload.messageId ? String(payload.messageId) : latestOpenRootId() || undefined;
          appendRuntimeEvent(
            event,
            responseMessageId || (payload.sessionId ? String(payload.sessionId) : undefined),
          );
          attachAgentToLatestRoot(agentId, event.timestamp);
          const message = (payload.content as string) || "";
          if (!message) return;
          setBubbles((current) =>
            [
              ...current,
              {
                id: `${event.timestamp}-${Math.random().toString(36).slice(2, 7)}`,
                agentId,
                message,
                timestamp: event.timestamp,
                targetAgents: extractTargets(message),
                messageId: responseMessageId,
                runId: payload.runId ? String(payload.runId) : undefined,
                sessionId: payload.sessionId ? String(payload.sessionId) : undefined,
              },
            ].slice(-200),
          );
        }

        if (event.type === "message:done") {
          const messageId = payload.messageId ? String(payload.messageId) : undefined;
          if (!messageId) return;
          const rootSession = rootSessionsRef.current.get(messageId);
          if (!rootSession) return;

          rootSession.completedAt = event.timestamp;
          openRootOrderRef.current = openRootOrderRef.current.filter((id) => id !== messageId);

          setAgentWorkSessions((current) => {
            const next = { ...current };
            rootSession.agentIds.forEach((sessionAgentId) => {
              const existing = next[sessionAgentId];
              if (!existing || existing.rootMessageId !== messageId) return;
              next[sessionAgentId] = { ...existing, completedAt: event.timestamp };
            });
            return next;
          });
        }
      },
      () => setConnected(false),
    );

    return unsubscribe;
  }, []);

  useEffect(() => {
    const interval = window.setInterval(() => {
      const cutoff = Date.now() - OFFICE_BUBBLE_RETENTION_MS;
      setBubbles((current) => current.filter((bubble) => bubble.timestamp > cutoff));
    }, 2000);
    return () => window.clearInterval(interval);
  }, []);

  return { bubbles, runtimeEvents, connected, clock, agentWorkSessions };
}
