"use client";

import { useEffect, useRef } from "react";
import { fetchRunState, getStreamUrl } from "@/lib/api";
import { useLeadSlayerStore } from "@/store/useLeadSlayerStore";
import type { StreamEvent, StreamEventType } from "@/types/contracts";

const STREAM_EVENTS: StreamEventType[] = [
  "phase_changed",
  "agent_log",
  "audit_completed",
  "icps_generated",
  "hunter_report",
  "leads_loaded",
  "lead_verdict",
  "email_drafted",
  "mcp_tool_call",
  "telemetry_update",
  "pipeline_completed",
  "pipeline_error",
];

const TERMINAL_PHASES = new Set(["IDLE", "READY", "DISPATCHED", "ERROR"]);

export function useLeadSlayerStream(): void {
  const runId = useLeadSlayerStore((s) => s.runId);
  const phase = useLeadSlayerStore((s) => s.phase);
  const executionMode = useLeadSlayerStore((s) => s.executionMode);
  const setExecutionMode = useLeadSlayerStore((s) => s.setExecutionMode);
  const applyStreamEvent = useLeadSlayerStore((s) => s.applyStreamEvent);
  const hydrateFromSnapshot = useLeadSlayerStore((s) => s.hydrateFromSnapshot);

  const lastEventIdRef = useRef<number>(0);
  const activeRunIdRef = useRef<string | null>(null);

  // Detect hidden ?mode=replay flag and Ctrl+Shift+M quick toggle
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("mode") === "replay") {
      setExecutionMode("SAFE_REPLAY");
    }

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "m") {
        e.preventDefault();
        const next = executionMode === "LIVE" ? "SAFE_REPLAY" : "LIVE";
        setExecutionMode(next);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [executionMode, setExecutionMode]);

  const isActiveRun = Boolean(runId) && !TERMINAL_PHASES.has(phase);

  useEffect(() => {
    if (!runId || !isActiveRun) {
      return;
    }

    if (activeRunIdRef.current !== runId) {
      activeRunIdRef.current = runId;
      lastEventIdRef.current = 0;
    }

    let errorStreak = 0;
    let closedManually = false;

    const es = new EventSource(getStreamUrl(runId));

    const handleIncoming = (rawEvent: MessageEvent<string>) => {
      errorStreak = 0;
      try {
        const parsed = JSON.parse(rawEvent.data) as StreamEvent;
        if (parsed.event_id <= lastEventIdRef.current) {
          return;
        }
        lastEventIdRef.current = parsed.event_id;
        applyStreamEvent(parsed);

        if (
          parsed.event_type === "pipeline_completed" ||
          parsed.event_type === "pipeline_error"
        ) {
          closedManually = true;
          es.close();
        }
      } catch {
        // Ignore malformed frame safely
      }
    };

    for (const eventType of STREAM_EVENTS) {
      es.addEventListener(eventType, handleIncoming as EventListener);
    }

    es.onerror = async () => {
      if (closedManually) return;
      errorStreak += 1;
      if (errorStreak >= 2) {
        closedManually = true;
        es.close();
        try {
          const snapshot = await fetchRunState(runId);
          hydrateFromSnapshot(snapshot);
        } catch {
          // Run state snapshot recovery failed silently; UI can retry
        }
      }
    };

    return () => {
      closedManually = true;
      es.close();
    };
  }, [runId, isActiveRun, applyStreamEvent, hydrateFromSnapshot]);
}
