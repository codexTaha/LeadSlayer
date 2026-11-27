"use client";

import { motion } from "framer-motion";
import { Loader2, Radar, ShieldCheck, Skull } from "lucide-react";
import { REJECTION_CATEGORY_LABELS } from "@/lib/constants";
import {
  useLeadSlayerStore,
  type CategoryFilter,
} from "@/store/useLeadSlayerStore";
import type { RejectionCategory } from "@/types/contracts";

const CATEGORIES: RejectionCategory[] = [
  "COMPETITOR_LOCK_IN",
  "TOO_SMALL",
  "LAYOFFS_FREEZE",
  "WRONG_PERSONA",
  "NO_STACK_FIT",
  "BUILT_IN_HOUSE",
  "NO_URGENCY_SIGNAL",
];

export function SlayerAutopsyBar() {
  const phase = useLeadSlayerStore((s) => s.phase);
  const telemetry = useLeadSlayerStore((s) => s.telemetry);
  const hunterReport = useLeadSlayerStore((s) => s.hunterReport);
  const leadCount = useLeadSlayerStore((s) => s.leadOrder.length);
  const activeFilter = useLeadSlayerStore((s) => s.activeCategoryFilter);
  const setActiveFilter = useLeadSlayerStore((s) => s.setActiveCategoryFilter);

  const total = telemetry?.total_leads ?? leadCount;
  const processed = telemetry?.processed_leads ?? 0;
  const killed = telemetry?.killed_count ?? 0;
  const survived = telemetry?.survived_count ?? 0;
  const killRate = telemetry?.kill_rate_pct ?? 0;
  const savedHours = telemetry?.estimated_saved_spam_hours ?? 0;
  const breakdown = telemetry?.rejection_breakdown ?? {};
  const slayerPct = total > 0 ? Math.min(100, (processed / total) * 100) : 0;

  const renderFilterPill = (
    key: CategoryFilter,
    label: string,
    count: number,
    tone: "neutral" | "green" | "red"
  ) => {
    const active = activeFilter === key;
    const baseTone =
      tone === "green"
        ? active
          ? "border-emerald-400 bg-emerald-500/20 text-emerald-200"
          : "border-emerald-500/30 bg-emerald-500/10 text-emerald-300/80 hover:border-emerald-400/60"
        : tone === "red"
          ? active
            ? "border-rose-400 bg-rose-500/20 text-rose-200"
            : "border-zinc-800 bg-zinc-900/70 text-zinc-300 hover:border-rose-500/40"
          : active
            ? "border-zinc-400 bg-zinc-800 text-zinc-50"
            : "border-zinc-800 bg-zinc-900/70 text-zinc-300 hover:border-zinc-600";

    return (
      <button
        key={key}
        type="button"
        onClick={() => setActiveFilter(key)}
        className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-[11px] font-mono transition cursor-pointer ${baseTone}`}
      >
        <span>{label}</span>
        <span className="rounded bg-black/35 px-1 py-0.2 text-[10px]">
          {count}
        </span>
      </button>
    );
  };

  return (
    <section className="rounded-xl border border-zinc-800 bg-zinc-950/90 p-4 space-y-3.5">
      {phase === "HUNTING" && (
        <div className="rounded-lg border border-indigo-500/35 bg-indigo-950/20 px-3 py-2.5 space-y-2">
          <div className="flex items-center justify-between text-xs font-mono text-indigo-200">
            <span className="inline-flex items-center gap-2">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-400" />
              Hunter Swarm scanning {total} leads with Dual-Polarity vector similarity...
            </span>
            <span className="text-[11px] text-indigo-300">
              60% ICP · 25% Struct · -15% Anti-ICP
            </span>
          </div>
          <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-indigo-950">
            <motion.div
              className="absolute inset-y-0 w-1/3 rounded-full bg-gradient-to-r from-transparent via-indigo-400 to-transparent"
              animate={{ x: ["-100%", "340%"] }}
              transition={{ duration: 1.3, repeat: Infinity, ease: "easeInOut" }}
            />
          </div>
        </div>
      )}

      {phase === "SLAYING" && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-950/15 px-3 py-2 space-y-1.5">
          <div className="flex items-center justify-between text-[11px] font-mono text-rose-200">
            <span className="inline-flex items-center gap-1.5">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-rose-400" />
              Slayer Swarm Adversarial Triage Active
            </span>
            <span>
              {processed}/{total} evaluated ({slayerPct.toFixed(0)}%)
            </span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-900">
            <motion.div
              className="h-full rounded-full bg-gradient-to-r from-rose-500 via-amber-400 to-emerald-400"
              initial={{ width: "0%" }}
              animate={{ width: `${slayerPct}%` }}
              transition={{ duration: 0.15, ease: "easeOut" }}
            />
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2">
          <div className="text-[10px] font-mono uppercase text-zinc-500">
            Processed
          </div>
          <div className="text-xl font-bold font-mono tabular-nums text-zinc-100">
            {processed}
            <span className="text-xs text-zinc-500">/{total}</span>
          </div>
        </div>

        <div className="rounded-lg border border-rose-500/30 bg-rose-950/25 px-3 py-2">
          <div className="flex items-center gap-1 text-[10px] font-mono uppercase text-rose-400">
            <Skull className="h-3 w-3" />
            Slaughtered
          </div>
          <div className="text-xl font-bold font-mono tabular-nums text-rose-400">
            {killed}
          </div>
        </div>

        <div className="rounded-lg border border-emerald-500/30 bg-emerald-950/25 px-3 py-2">
          <div className="flex items-center gap-1 text-[10px] font-mono uppercase text-emerald-400">
            <ShieldCheck className="h-3 w-3" />
            Survivors
          </div>
          <div className="text-xl font-bold font-mono tabular-nums text-emerald-400">
            {survived}
          </div>
        </div>

        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2">
          <div className="text-[10px] font-mono uppercase text-zinc-500">
            Kill Rate
          </div>
          <div className="text-xl font-bold font-mono tabular-nums text-amber-300">
            {killRate.toFixed(1)}%
          </div>
        </div>

        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 px-3 py-2 col-span-2 sm:col-span-1">
          <div className="text-[10px] font-mono uppercase text-zinc-500">
            Research Saved
          </div>
          <div className="text-xl font-bold font-mono tabular-nums text-sky-300">
            {savedHours.toFixed(1)}h
          </div>
        </div>
      </div>

      {hunterReport && hunterReport.hunt_queries.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-zinc-800/80 bg-zinc-900/40 px-3 py-2 text-[11px]">
          <span className="inline-flex items-center gap-1 font-mono uppercase text-indigo-300 shrink-0">
            <Radar className="h-3.5 w-3.5" />
            Hunter Signals:
          </span>
          {(hunterReport.autonomous_discovered_leads ?? 0) > 0 && (
            <span className="rounded border border-emerald-500/40 bg-emerald-500/15 px-2 py-0.5 font-mono text-emerald-200">
              Auto-Discovered: {hunterReport.autonomous_discovered_leads} real companies ({hunterReport.url_fetches_succeeded} live sites)
            </span>
          )}
          {hunterReport.hunt_queries.slice(0, 3).map((q, idx) => (
            <span
              key={idx}
              className="rounded border border-zinc-800 bg-zinc-950 px-2 py-0.5 font-mono text-zinc-300"
            >
              <span className="text-zinc-500">{q.source}:</span> {q.query_string}
            </span>
          ))}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-1.5">
        {renderFilterPill("ALL", "ALL", total, "neutral")}
        {renderFilterPill("SURVIVED", "SURVIVED", survived, "green")}
        {CATEGORIES.map((cat) => {
          const count = breakdown[cat] ?? 0;
          if (count === 0 && activeFilter !== cat) return null;
          return renderFilterPill(
            cat,
            REJECTION_CATEGORY_LABELS[cat],
            count,
            "red"
          );
        })}
      </div>
    </section>
  );
}
