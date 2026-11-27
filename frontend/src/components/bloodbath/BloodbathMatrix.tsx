"use client";

import { motion } from "framer-motion";
import { ArrowRight, Download, Globe, Search } from "lucide-react";
import { LeadTile } from "@/components/bloodbath/LeadTile";
import { SlayerAutopsyBar } from "@/components/bloodbath/SlayerAutopsyBar";
import { getExportUrl } from "@/lib/api";
import { useLeadSlayerStore } from "@/store/useLeadSlayerStore";

export function BloodbathMatrix() {
  const runId = useLeadSlayerStore((s) => s.runId);
  const leadOrder = useLeadSlayerStore((s) => s.leadOrder);
  const phase = useLeadSlayerStore((s) => s.phase);
  const setActiveViewTab = useLeadSlayerStore((s) => s.setActiveViewTab);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <span className="text-[11px] font-mono uppercase tracking-wider text-rose-400">
            {phase === "HUNTING"
              ? "Step 3 · Hunter Swarm & Dual-Polarity Vector Scoring"
              : "Act 2 · Disqualification Matrix (gemini-3.5-flash-lite)"}
          </span>
          <h2 className="text-lg font-bold text-zinc-50">
            {phase === "HUNTING"
              ? "Hunter Swarm — Generating Queries & Computing Vector Fit Across 50 Leads"
              : "The Bloodbath — Click Any Tile for Forensic Autopsy or Resurrect"}
          </h2>
        </div>

        {(phase === "READY" || phase === "DISPATCHED" || phase === "SNIPING") && (
          <div className="flex flex-wrap items-center gap-2">
            {runId && (
              <a
                href={getExportUrl(runId, "csv")}
                download
                className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-900 px-3.5 py-2 text-xs font-medium text-zinc-200 hover:border-emerald-500/50 hover:bg-zinc-800 transition"
              >
                <Download className="h-3.5 w-3.5 text-emerald-400" />
                Download Verified Leads (.CSV)
              </a>
            )}
            <button
              type="button"
              onClick={() => {
                setActiveViewTab("SNIPER");
              }}
              className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-500/50 bg-emerald-500/15 px-3.5 py-2 text-xs font-semibold text-emerald-200 hover:bg-emerald-500/25 cursor-pointer"
            >
              Open Sniper Command Deck
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>

      <SlayerAutopsyBar />

      {leadOrder.length === 0 && phase === "HUNTING" ? (
        <div className="rounded-xl border border-indigo-500/35 bg-zinc-950/90 p-8 text-center space-y-4">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-indigo-500/40 bg-indigo-500/15">
            <Search className="h-5 w-5 text-indigo-300 animate-pulse" />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-zinc-100 inline-flex items-center gap-2">
              <Globe className="h-4 w-4 text-emerald-400" />
              Autonomous Google Search &amp; Live Website Verification Running...
            </h3>
            <p className="text-xs text-zinc-400 max-w-lg mx-auto">
              Discovering real companies from Step 2 ICPs, verifying live domains over HTTP, and extracting public emails &amp; tech signals.
            </p>
          </div>
          <div className="mx-auto max-w-md h-1.5 overflow-hidden rounded-full bg-indigo-950">
            <motion.div
              className="h-full w-1/3 rounded-full bg-gradient-to-r from-transparent via-indigo-400 to-transparent"
              animate={{ x: ["-100%", "340%"] }}
              transition={{ duration: 1.3, repeat: Infinity, ease: "easeInOut" }}
            />
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-5 lg:grid-cols-10 gap-2">
          {leadOrder.map((leadId, idx) => (
            <LeadTile key={leadId} leadId={leadId} index={idx} />
          ))}
        </div>
      )}
    </div>
  );
}
