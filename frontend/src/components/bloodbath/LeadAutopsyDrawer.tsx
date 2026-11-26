"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Building2,
  CheckCircle2,
  Loader2,
  RotateCcw,
  Skull,
  Sparkles,
  X,
} from "lucide-react";
import { resurrectLead } from "@/lib/api";
import { REJECTION_CATEGORY_LABELS } from "@/lib/constants";
import { useLeadSlayerStore } from "@/store/useLeadSlayerStore";

export function LeadAutopsyDrawer() {
  const runId = useLeadSlayerStore((s) => s.runId);
  const selectedLeadId = useLeadSlayerStore((s) => s.selectedLeadId);
  const lead = useLeadSlayerStore((s) =>
    s.selectedLeadId ? s.leadsById[s.selectedLeadId] : undefined
  );
  const verdict = useLeadSlayerStore((s) =>
    s.selectedLeadId ? s.verdictsById[s.selectedLeadId] : undefined
  );
  const setSelectedLeadId = useLeadSlayerStore((s) => s.setSelectedLeadId);
  const applyResurrection = useLeadSlayerStore((s) => s.applyResurrection);
  const setError = useLeadSlayerStore((s) => s.setError);

  const [isResurrecting, setIsResurrecting] = useState(false);

  const handleResurrect = async () => {
    if (!runId || !selectedLeadId) return;
    setIsResurrecting(true);
    setError(null);
    try {
      const res = await resurrectLead(runId, selectedLeadId);
      applyResurrection(res);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to resurrect lead via Sniper."
      );
    } finally {
      setIsResurrecting(false);
    }
  };

  return (
    <AnimatePresence>
      {selectedLeadId && lead && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSelectedLeadId(null)}
            className="fixed inset-0 z-40 bg-black/65 backdrop-blur-xs"
          />

          <motion.aside
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 28, stiffness: 280 }}
            className="fixed right-0 top-0 bottom-0 z-50 w-full max-w-md border-l border-zinc-800 bg-[#0B0E14] p-6 shadow-2xl overflow-y-auto flex flex-col justify-between gap-6"
          >
            <div className="space-y-5">
              <div className="flex items-start justify-between gap-3 border-b border-zinc-800 pb-4">
                <div>
                  <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">
                    Forensic Lead Autopsy · {lead.id}
                  </span>
                  <h3 className="text-lg font-bold text-zinc-50 mt-0.5">
                    {lead.full_name}
                  </h3>
                  <p className="text-xs text-zinc-400">
                    {lead.role} @ {lead.company}
                  </p>
                </div>

                <button
                  type="button"
                  aria-label="Close autopsy drawer"
                  onClick={() => setSelectedLeadId(null)}
                  className="rounded-lg border border-zinc-800 p-1.5 text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100 cursor-pointer"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-3.5 space-y-2 text-xs">
                <div className="flex items-center justify-between text-zinc-300">
                  <span className="inline-flex items-center gap-1.5">
                    <Building2 className="h-3.5 w-3.5 text-zinc-500" />
                    {lead.industry} · {lead.funding_stage}
                  </span>
                  <span className="font-mono text-zinc-400">
                    {lead.employee_count} employees
                  </span>
                </div>
                <div className="flex flex-wrap gap-1 pt-1">
                  {lead.tech_stack.map((tech) => (
                    <span
                      key={tech}
                      className="rounded border border-zinc-800 bg-zinc-950 px-1.5 py-0.5 font-mono text-[10px] text-zinc-300"
                    >
                      {tech}
                    </span>
                  ))}
                </div>
                <div className="pt-2 border-t border-zinc-800/80">
                  <div className="text-[10px] font-mono uppercase text-zinc-500 mb-1">
                    Observed Market Signal
                  </div>
                  <p className="text-zinc-200 leading-relaxed">
                    {lead.recent_signal || "No recent signal provided."}
                  </p>
                </div>
                {lead.bio_snippet && (
                  <p className="text-zinc-400 italic">{lead.bio_snippet}</p>
                )}
              </div>

              {verdict ? (
                <div className="space-y-4">
                  <div
                    className={`rounded-xl border p-4 space-y-2 ${
                      verdict.survived
                        ? "border-emerald-500/40 bg-emerald-950/25"
                        : "border-rose-500/40 bg-rose-950/25"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span
                        className={`inline-flex items-center gap-1.5 text-xs font-mono font-semibold ${
                          verdict.survived
                            ? "text-emerald-300"
                            : "text-rose-300"
                        }`}
                      >
                        {verdict.survived ? (
                          <CheckCircle2 className="h-4 w-4" />
                        ) : (
                          <Skull className="h-4 w-4" />
                        )}
                        {verdict.headline_tag}
                      </span>
                      <span className="font-mono text-sm font-bold text-zinc-100">
                        {verdict.qualification_score}/100
                      </span>
                    </div>

                    {verdict.rejection_category && !verdict.survived && (
                      <div className="text-[11px] font-mono text-rose-200/80">
                        Category:{" "}
                        {REJECTION_CATEGORY_LABELS[verdict.rejection_category]}
                      </div>
                    )}

                    <p className="text-xs text-zinc-200 leading-relaxed">
                      {verdict.reasoning}
                    </p>
                  </div>

                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 space-y-2.5">
                    <div className="text-[10px] font-mono uppercase tracking-wider text-zinc-400">
                      Stage 2 Mathematical Vector Breakdown
                    </div>
                    {(
                      [
                        [
                          "ICP Vector Match",
                          Math.round(verdict.icp_similarity_score * 100),
                          "bg-emerald-400",
                        ],
                        [
                          "Structural Stack/Size Fit",
                          Math.round(verdict.structural_match_score * 100),
                          "bg-sky-400",
                        ],
                        [
                          "Anti-ICP Risk Penalty",
                          Math.round(verdict.anti_icp_similarity_score * 100),
                          "bg-rose-400",
                        ],
                        [
                          "Slayer Verdict Confidence",
                          Math.round(verdict.confidence * 100),
                          "bg-amber-400",
                        ],
                      ] as const
                    ).map(([label, pct, barColor]) => (
                      <div key={label} className="space-y-1 text-xs">
                        <div className="flex justify-between">
                          <span className="text-zinc-400">{label}</span>
                          <span className="font-mono text-zinc-200">
                            {pct}%
                          </span>
                        </div>
                        <div className="h-1.5 w-full rounded-full bg-zinc-800 overflow-hidden">
                          <div
                            className={`h-full rounded-full ${barColor}`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 text-xs text-zinc-400">
                  Awaiting Slayer verdict...
                </div>
              )}
            </div>

            {verdict && !verdict.survived && runId && (
              <div className="border-t border-zinc-800 pt-4">
                <button
                  type="button"
                  disabled={isResurrecting}
                  onClick={handleResurrect}
                  className="w-full inline-flex items-center justify-center gap-2 rounded-xl border border-amber-500/50 bg-amber-500/15 px-4 py-3 text-sm font-semibold text-amber-200 hover:bg-amber-500/25 transition cursor-pointer disabled:opacity-50"
                >
                  {isResurrecting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <RotateCcw className="h-4 w-4" />
                  )}
                  {isResurrecting
                    ? "Invoking Sniper (gemini-4-hydrogen)..."
                    : "Resurrect Lead & Draft Email"}
                  <Sparkles className="h-4 w-4 text-amber-400" />
                </button>
              </div>
            )}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
