"use client";

import { motion } from "framer-motion";
import { ArrowLeft, Crosshair, Loader2 } from "lucide-react";
import { DispatchExportBar } from "@/components/sniper/DispatchExportBar";
import { MCPDecisionsPanel } from "@/components/sniper/MCPDecisionsPanel";
import { SniperEmailCard } from "@/components/sniper/SniperEmailCard";
import { useLeadSlayerStore } from "@/store/useLeadSlayerStore";

export function SniperDeck() {
  const phase = useLeadSlayerStore((s) => s.phase);
  const leadOrder = useLeadSlayerStore((s) => s.leadOrder);
  const emailsById = useLeadSlayerStore((s) => s.emailsById);
  const telemetry = useLeadSlayerStore((s) => s.telemetry);
  const setActiveViewTab = useLeadSlayerStore((s) => s.setActiveViewTab);

  const orderedDrafts = leadOrder
    .map((id) => emailsById[id])
    .filter((d): d is NonNullable<typeof d> => Boolean(d));
  const targetSurvivors = telemetry?.survived_count ?? orderedDrafts.length;
  const sniperPct =
    targetSurvivors > 0
      ? Math.min(100, (orderedDrafts.length / targetSurvivors) * 100)
      : 0;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <span className="text-[11px] font-mono uppercase tracking-wider text-emerald-400">
            Act 3 · Sniper Command Deck (gemini-4-hydrogen + Vector Grounding)
          </span>
          <h2 className="text-lg font-bold text-zinc-50 flex items-center gap-2">
            <Crosshair className="h-5 w-5 text-emerald-400" />
            {orderedDrafts.length} Hyper-Personalized Emails Ready —{" "}
            {telemetry?.killed_count ?? 0} Bad Leads Blocked
          </h2>
        </div>

        <button
          type="button"
          onClick={() => setActiveViewTab("BLOODBATH")}
          className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-900 px-3.5 py-2 text-xs font-medium text-zinc-200 hover:bg-zinc-800 cursor-pointer"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          Back to 50-Tile Bloodbath
        </button>
      </div>

      {phase === "SNIPING" && (
        <div className="rounded-xl border border-emerald-500/35 bg-emerald-950/20 px-4 py-3 space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-mono text-emerald-300">
            <span className="inline-flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              Sniper Agent retrieving Stage 2 product chunks &amp; drafting evidence-backed outreach...
            </span>
            <span>
              {orderedDrafts.length}/{targetSurvivors || "?"} drafted
            </span>
          </div>
          <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-emerald-950">
            {orderedDrafts.length === 0 ? (
              <motion.div
                className="absolute inset-y-0 w-1/3 rounded-full bg-gradient-to-r from-transparent via-emerald-400 to-transparent"
                animate={{ x: ["-100%", "340%"] }}
                transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
              />
            ) : (
              <motion.div
                className="h-full rounded-full bg-emerald-400"
                initial={{ width: "0%" }}
                animate={{ width: `${sniperPct}%` }}
                transition={{ duration: 0.25, ease: "easeOut" }}
              />
            )}
          </div>
        </div>
      )}

      {orderedDrafts.length === 0 && phase === "SNIPING" ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {[0, 1].map((idx) => (
            <div
              key={idx}
              className="rounded-2xl border border-emerald-500/20 bg-zinc-950/80 p-5 space-y-3 animate-pulse"
            >
              <div className="h-4 w-40 rounded bg-zinc-800" />
              <div className="h-3 w-64 rounded bg-zinc-900" />
              <div className="h-8 w-full rounded bg-zinc-900" />
              <div className="h-20 w-full rounded bg-zinc-900/70" />
            </div>
          ))}
        </div>
      ) : orderedDrafts.length === 0 ? (
        <div className="rounded-xl border border-zinc-800 bg-zinc-950/80 p-8 text-center text-sm text-zinc-400">
          No survivor emails drafted yet. Run the Bloodbath or resurrect a killed lead from the 50-tile matrix.
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {orderedDrafts.map((draft) => (
            <SniperEmailCard key={draft.lead_id} draft={draft} />
          ))}
        </div>
      )}

      <MCPDecisionsPanel />

      <DispatchExportBar />
    </div>
  );
}
