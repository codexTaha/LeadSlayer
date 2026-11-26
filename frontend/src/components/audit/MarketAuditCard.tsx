"use client";

import { motion } from "framer-motion";
import { Globe, Search, ShieldAlert, Swords, Target } from "lucide-react";
import { useLeadSlayerStore } from "@/store/useLeadSlayerStore";

const SEVERITY_BADGE: Record<string, string> = {
  HIGH: "border-rose-500/50 bg-rose-500/15 text-rose-300",
  MEDIUM: "border-amber-500/50 bg-amber-500/15 text-amber-300",
  LOW: "border-zinc-600 bg-zinc-800 text-zinc-300",
};

export function MarketAuditCard() {
  const audit = useLeadSlayerStore((s) => s.marketAudit);
  if (!audit) return null;

  return (
    <motion.section
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="rounded-xl border border-zinc-800 bg-zinc-950/90 p-5 space-y-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-zinc-800/80 pb-4">
        <div className="space-y-1.5 max-w-2xl">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-mono uppercase tracking-wider text-indigo-400">
              Step 1 · Market Auditor (gemini-4-hydrogen)
            </span>
            {audit.url_scraped_context_used && (
              <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-mono text-emerald-300">
                <Globe className="h-3 w-3" />
                Live Site Read
              </span>
            )}
            {audit.search_grounding_used && (
              <span className="inline-flex items-center gap-1 rounded-full border border-sky-500/40 bg-sky-500/10 px-2 py-0.5 text-[10px] font-mono text-sky-300">
                <Search className="h-3 w-3" />
                Search Grounded
              </span>
            )}
          </div>
          <h2 className="text-lg font-semibold text-zinc-50">
            {audit.sharpened_value_prop}
          </h2>
          <p className="text-sm text-zinc-400 leading-relaxed">
            {audit.market_reality_summary}
          </p>
        </div>

        <div className="flex flex-col items-end rounded-xl border border-zinc-800 bg-zinc-900/70 px-4 py-2.5">
          <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-400">
            Readiness Score
          </span>
          <span className="text-2xl font-bold font-mono text-emerald-400">
            {audit.market_readiness_score}
            <span className="text-xs text-zinc-500">/100</span>
          </span>
        </div>
      </div>

      {audit.readiness_breakdown && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {(
            [
              ["Pain Urgency", audit.readiness_breakdown.pain_urgency],
              ["ICP Clarity", audit.readiness_breakdown.icp_clarity],
              ["Differentiation", audit.readiness_breakdown.differentiation],
              ["Timing Fit", audit.readiness_breakdown.timing_fit],
            ] as const
          ).map(([label, val]) => (
            <div
              key={label}
              className="rounded-lg border border-zinc-800/80 bg-zinc-900/50 p-2.5"
            >
              <div className="flex items-center justify-between text-xs mb-1.5">
                <span className="text-zinc-400">{label}</span>
                <span className="font-mono text-zinc-200">{val}%</span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-zinc-800 overflow-hidden">
                <div
                  className="h-full rounded-full bg-indigo-400"
                  style={{ width: `${val}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {audit.assumption_gaps.length > 0 ? (
        <div className="space-y-2.5">
          <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-zinc-300">
            <Target className="h-3.5 w-3.5 text-amber-400" />
            Assumption vs. Reality Gap Analysis
          </div>
          <div className="grid grid-cols-1 gap-2.5">
            {audit.assumption_gaps.map((gap, idx) => (
              <div
                key={idx}
                className="grid grid-cols-1 md:grid-cols-12 gap-3 rounded-lg border border-zinc-800 bg-zinc-900/50 p-3 text-xs"
              >
                <div className="md:col-span-4 space-y-1">
                  <span className="text-[10px] font-mono uppercase text-zinc-500">
                    Founder Assumed
                  </span>
                  <p className="text-zinc-300 line-through decoration-rose-500/60">
                    {gap.founder_belief}
                  </p>
                </div>
                <div className="md:col-span-4 space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono uppercase text-zinc-500">
                      Market Reality
                    </span>
                    <span
                      className={`rounded border px-1.5 py-0.2 text-[9px] font-mono ${
                        SEVERITY_BADGE[gap.severity] || SEVERITY_BADGE.HIGH
                      }`}
                    >
                      {gap.severity}
                    </span>
                  </div>
                  <p className="text-zinc-100">{gap.market_reality}</p>
                </div>
                <div className="md:col-span-4 space-y-1">
                  <span className="text-[10px] font-mono uppercase text-emerald-400/90">
                    Strategic Fix
                  </span>
                  <p className="text-emerald-200/90">{gap.strategic_fix}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-amber-300">
            <ShieldAlert className="h-3.5 w-3.5" />
            Founder Blind Spots Exposed
          </div>
          <ul className="space-y-1.5 text-xs text-zinc-300">
            {audit.founder_blind_spots.map((spot, i) => (
              <li
                key={i}
                className="rounded-lg border border-zinc-800 bg-zinc-900/40 px-3 py-2"
              >
                {spot}
              </li>
            ))}
          </ul>
        </div>
      )}

      {audit.competitor_landscape.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-zinc-300">
            <Swords className="h-3.5 w-3.5 text-rose-400" />
            Competitor Wedge &amp; Switching Triggers
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
            {audit.competitor_landscape.map((comp, idx) => (
              <div
                key={idx}
                className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-3 space-y-1.5 text-xs"
              >
                <div className="font-semibold text-zinc-100">{comp.name}</div>
                <p className="text-zinc-400">
                  <span className="text-zinc-500">Weakness:</span>{" "}
                  {comp.positioning_weakness}
                </p>
                <p className="text-emerald-300/90">
                  <span className="text-emerald-500">Wedge:</span>{" "}
                  {comp.switching_trigger}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </motion.section>
  );
}
