"use client";

import { useEffect, useRef } from "react";
import { ArrowRight } from "lucide-react";
import { LeadTile } from "@/components/bloodbath/LeadTile";
import { SlayerAutopsyBar } from "@/components/bloodbath/SlayerAutopsyBar";
import { useLeadSlayerStore } from "@/store/useLeadSlayerStore";

export function BloodbathMatrix() {
  const leadOrder = useLeadSlayerStore((s) => s.leadOrder);
  const phase = useLeadSlayerStore((s) => s.phase);
  const selectedLeadId = useLeadSlayerStore((s) => s.selectedLeadId);
  const activeViewTab = useLeadSlayerStore((s) => s.activeViewTab);
  const setActiveViewTab = useLeadSlayerStore((s) => s.setActiveViewTab);

  const autoAdvancedRef = useRef(false);

  // Reset auto-advance guard when a new run starts
  useEffect(() => {
    if (phase === "IDLE" || phase === "AUDITING" || phase === "SLAYING") {
      autoAdvancedRef.current = false;
    }
  }, [phase]);

  // Hold 2.0s after Bloodbath completes so judges see final 42/8 matrix, then glide to Sniper Deck
  useEffect(() => {
    if (
      phase !== "READY" ||
      activeViewTab !== "BLOODBATH" ||
      selectedLeadId !== null ||
      autoAdvancedRef.current
    ) {
      return;
    }

    const timer = window.setTimeout(() => {
      autoAdvancedRef.current = true;
      setActiveViewTab("SNIPER");
    }, 2000);

    return () => window.clearTimeout(timer);
  }, [phase, activeViewTab, selectedLeadId, setActiveViewTab]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <span className="text-[11px] font-mono uppercase tracking-wider text-rose-400">
            Act 2 · Disqualification Matrix (gemini-3.5-flash-lite)
          </span>
          <h2 className="text-lg font-bold text-zinc-50">
            The Bloodbath — Click Any Tile for Forensic Autopsy or Resurrect
          </h2>
        </div>

        {(phase === "READY" || phase === "DISPATCHED" || phase === "SNIPING") && (
          <button
            type="button"
            onClick={() => {
              autoAdvancedRef.current = true;
              setActiveViewTab("SNIPER");
            }}
            className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-500/50 bg-emerald-500/15 px-3.5 py-2 text-xs font-semibold text-emerald-200 hover:bg-emerald-500/25 cursor-pointer"
          >
            Open Sniper Command Deck
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      <SlayerAutopsyBar />

      <div className="grid grid-cols-2 sm:grid-cols-5 lg:grid-cols-10 gap-2">
        {leadOrder.map((leadId) => (
          <LeadTile key={leadId} leadId={leadId} />
        ))}
      </div>
    </div>
  );
}
