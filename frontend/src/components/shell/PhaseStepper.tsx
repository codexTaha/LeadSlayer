"use client";

import { Check, Loader2 } from "lucide-react";
import { PHASE_STEP_ORDER } from "@/lib/constants";
import { useLeadSlayerStore } from "@/store/useLeadSlayerStore";
import type { PipelinePhase } from "@/types/contracts";

const PHASE_RANK: Record<PipelinePhase, number> = {
  IDLE: 0,
  AUDITING: 1,
  ICP_GENERATION: 2,
  HUNTING: 3,
  SLAYING: 4,
  SNIPING: 5,
  READY: 6,
  DISPATCHED: 7,
  ERROR: 0,
};

export function PhaseStepper() {
  const phase = useLeadSlayerStore((s) => s.phase);
  const activeViewTab = useLeadSlayerStore((s) => s.activeViewTab);
  const setActiveViewTab = useLeadSlayerStore((s) => s.setActiveViewTab);

  const currentRank = PHASE_RANK[phase];

  return (
    <nav
      aria-label="Pipeline phases"
      className="flex items-center gap-1.5 overflow-x-auto py-1"
    >
      {PHASE_STEP_ORDER.map((step, idx) => {
        const stepRank = idx + 1;
        const isCurrent = step.phases.includes(phase);
        const isCompleted =
          currentRank > stepRank && phase !== "ERROR" && phase !== "IDLE";
        const isSelectedView = activeViewTab === step.viewTab;
        const isClickable = currentRank >= 1 || step.viewTab === "AUDIT";

        return (
          <button
            key={step.id}
            type="button"
            disabled={!isClickable}
            onClick={() => setActiveViewTab(step.viewTab)}
            className={`group flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs font-medium transition-all whitespace-nowrap ${
              isCurrent
                ? "border-rose-500/70 bg-rose-500/15 text-rose-200 shadow-[0_0_16px_rgba(244,63,94,0.18)]"
                : isSelectedView && phase !== "IDLE"
                  ? "border-zinc-600 bg-zinc-800/90 text-zinc-100"
                  : isCompleted
                    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300 hover:border-emerald-500/50"
                    : "border-zinc-800/80 bg-zinc-900/40 text-zinc-500"
            } ${isClickable ? "cursor-pointer" : "cursor-not-allowed opacity-60"}`}
          >
            {isCurrent && phase !== "READY" && phase !== "DISPATCHED" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-rose-400" />
            ) : isCompleted || (isCurrent && (phase === "READY" || phase === "DISPATCHED")) ? (
              <Check className="h-3.5 w-3.5 text-emerald-400" />
            ) : (
              <span className="h-1.5 w-1.5 rounded-full bg-current opacity-60" />
            )}
            <span>{step.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
