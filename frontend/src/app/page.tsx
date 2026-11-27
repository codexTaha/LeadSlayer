"use client";

import { useCallback, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, ChevronUp, Cpu, Terminal } from "lucide-react";
import { AuditWorkspace } from "@/components/audit/AuditWorkspace";
import { BloodbathMatrix } from "@/components/bloodbath/BloodbathMatrix";
import { LeadAutopsyDrawer } from "@/components/bloodbath/LeadAutopsyDrawer";
import { CommandCenterShell } from "@/components/shell/CommandCenterShell";
import { SniperDeck } from "@/components/sniper/SniperDeck";
import { useLeadSlayerStream } from "@/hooks/useLeadSlayerStream";
import { startPipeline } from "@/lib/api";
import { useLeadSlayerStore } from "@/store/useLeadSlayerStore";
import type { PipelinePhase } from "@/types/contracts";

const ACTIVE_ENGINE_BADGE: Partial<Record<PipelinePhase, { model: string; task: string }>> = {
  AUDITING: {
    model: "gemini-4-hydrogen",
    task: "Auditing market reality, gap analysis & Anti-ICP red flags",
  },
  ICP_GENERATION: {
    model: "gemini-4-hydrogen + gemini-embedding-2",
    task: "Synthesizing 3 ICPs & indexing 768d vectors into memory",
  },
  HUNTING: {
    model: "gemini-3.5-flash-lite + NumPy",
    task: "Generating hunt queries & Dual-Polarity cosine scoring",
  },
  SLAYING: {
    model: "gemini-3.5-flash-lite",
    task: "Adversarial triage across 50 leads (Keep/Kill + Reasoning)",
  },
  SNIPING: {
    model: "gemini-4-hydrogen + Stage 2 RAG",
    task: "Retrieving top-2 product chunks & drafting grounded outreach",
  },
};

export default function CommandCenterPage() {
  useLeadSlayerStream();

  const phase = useLeadSlayerStore((s) => s.phase);
  const activeViewTab = useLeadSlayerStore((s) => s.activeViewTab);
  const startupInput = useLeadSlayerStore((s) => s.startupInput);
  const agentLogs = useLeadSlayerStore((s) => s.agentLogs);
  const setIsStartingRun = useLeadSlayerStore((s) => s.setIsStartingRun);
  const beginRun = useLeadSlayerStore((s) => s.beginRun);
  const setError = useLeadSlayerStore((s) => s.setError);

  const [logsExpanded, setLogsExpanded] = useState(false);

  const handleLaunch = useCallback(async () => {
    setIsStartingRun(true);
    setError(null);
    try {
      const { run_id } = await startPipeline(startupInput);
      beginRun(run_id);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to start pipeline."
      );
      setIsStartingRun(false);
    }
  }, [startupInput, beginRun, setError, setIsStartingRun]);

  const activeEngine = ACTIVE_ENGINE_BADGE[phase];

  return (
    <CommandCenterShell onRetryRun={handleLaunch}>
      {activeEngine && (
        <div className="mb-5 rounded-xl border border-indigo-500/35 bg-indigo-950/20 px-4 py-3 space-y-2 overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-xs font-mono text-indigo-200">
              <Cpu className="h-4 w-4 text-indigo-400 animate-pulse" />
              <span className="font-semibold">LIVE PIPELINE:</span>
              <span>{activeEngine.task}</span>
            </div>
            <span className="rounded-md border border-indigo-500/40 bg-indigo-500/15 px-2 py-0.5 text-[11px] font-mono text-indigo-300">
              {activeEngine.model}
            </span>
          </div>

          <div className="relative h-1 w-full overflow-hidden rounded-full bg-indigo-950/80">
            <motion.div
              className="absolute inset-y-0 w-1/3 rounded-full bg-gradient-to-r from-transparent via-indigo-400 to-transparent"
              animate={{ x: ["-100%", "350%"] }}
              transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
            />
          </div>

          {agentLogs.length > 0 && (
            <div className="space-y-0.5 border-t border-indigo-500/20 pt-2 font-mono text-[11px] text-zinc-300">
              {agentLogs.slice(-4).map((log, i) => (
                <div key={i} className="truncate">
                  <span className="text-indigo-400 mr-1.5">&gt;</span>
                  {log}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <AnimatePresence mode="wait">
        {activeViewTab === "AUDIT" && (
          <motion.div
            key="view-audit"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
          >
            <AuditWorkspace onLaunch={handleLaunch} />
          </motion.div>
        )}

        {activeViewTab === "BLOODBATH" && (
          <motion.div
            key="view-bloodbath"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
          >
            <BloodbathMatrix />
          </motion.div>
        )}

        {activeViewTab === "SNIPER" && (
          <motion.div
            key="view-sniper"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
          >
            <SniperDeck />
          </motion.div>
        )}
      </AnimatePresence>

      {agentLogs.length > 0 && !activeEngine && (
        <div className="mt-6 rounded-xl border border-zinc-800/80 bg-zinc-950/70">
          <button
            type="button"
            onClick={() => setLogsExpanded((v) => !v)}
            className="flex w-full items-center justify-between px-4 py-2.5 text-xs font-mono text-zinc-400 hover:text-zinc-200 cursor-pointer"
          >
            <span className="inline-flex items-center gap-2">
              <Terminal className="h-3.5 w-3.5 text-zinc-500" />
              ADK Execution Trace ({agentLogs.length} events) ·{" "}
              <span className="text-zinc-300 truncate max-w-md">
                {agentLogs[agentLogs.length - 1]}
              </span>
            </span>
            {logsExpanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </button>

          {logsExpanded && (
            <div className="max-h-44 overflow-y-auto border-t border-zinc-800/80 px-4 py-2.5 space-y-1 font-mono text-[11px] text-zinc-400">
              {agentLogs.map((log, i) => (
                <div key={i}>{log}</div>
              ))}
            </div>
          )}
        </div>
      )}

      <LeadAutopsyDrawer />
    </CommandCenterShell>
  );
}
