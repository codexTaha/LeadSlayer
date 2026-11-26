"use client";

import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, ChevronUp, Terminal } from "lucide-react";
import { AuditWorkspace } from "@/components/audit/AuditWorkspace";
import { BloodbathMatrix } from "@/components/bloodbath/BloodbathMatrix";
import { LeadAutopsyDrawer } from "@/components/bloodbath/LeadAutopsyDrawer";
import { CommandCenterShell } from "@/components/shell/CommandCenterShell";
import { SniperDeck } from "@/components/sniper/SniperDeck";
import { useLeadSlayerStream } from "@/hooks/useLeadSlayerStream";
import { fetchDemoPreset, startPipeline } from "@/lib/api";
import { useLeadSlayerStore } from "@/store/useLeadSlayerStore";

export default function CommandCenterPage() {
  useLeadSlayerStream();

  const activeViewTab = useLeadSlayerStore((s) => s.activeViewTab);
  const startupInput = useLeadSlayerStore((s) => s.startupInput);
  const leadOrder = useLeadSlayerStore((s) => s.leadOrder);
  const agentLogs = useLeadSlayerStore((s) => s.agentLogs);
  const setPresetData = useLeadSlayerStore((s) => s.setPresetData);
  const setIsLoadingPreset = useLeadSlayerStore((s) => s.setIsLoadingPreset);
  const setIsStartingRun = useLeadSlayerStore((s) => s.setIsStartingRun);
  const beginRun = useLeadSlayerStore((s) => s.beginRun);
  const setError = useLeadSlayerStore((s) => s.setError);

  const [logsExpanded, setLogsExpanded] = useState(false);

  const loadDefaultPreset = useCallback(async () => {
    setIsLoadingPreset(true);
    try {
      const preset = await fetchDemoPreset();
      setPresetData(preset.startup, preset.leads);
    } catch {
      // Non-fatal on initial mount; user can click Load Preset button
    } finally {
      setIsLoadingPreset(false);
    }
  }, [setIsLoadingPreset, setPresetData]);

  useEffect(() => {
    if (leadOrder.length === 0 && !startupInput.product_name) {
      void loadDefaultPreset();
    }
  }, [leadOrder.length, startupInput.product_name, loadDefaultPreset]);

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

  return (
    <CommandCenterShell onRetryRun={handleLaunch}>
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

      {agentLogs.length > 0 && (
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
