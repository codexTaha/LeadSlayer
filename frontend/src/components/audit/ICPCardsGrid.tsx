"use client";

import { motion } from "framer-motion";
import { Cpu, Layers, Users, Zap } from "lucide-react";
import { useLeadSlayerStore } from "@/store/useLeadSlayerStore";

export function ICPCardsGrid() {
  const icps = useLeadSlayerStore((s) => s.icps);
  if (icps.length === 0) return null;

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-mono uppercase tracking-wider text-emerald-400">
          Step 2 · 3 Ideal Customer Profiles Locked Into Vector Memory (gemini-embedding-2)
        </span>
      </div>

      <motion.div
        initial="hidden"
        animate="visible"
        variants={{
          hidden: {},
          visible: { transition: { staggerChildren: 0.08 } },
        }}
        className="grid grid-cols-1 md:grid-cols-3 gap-4"
      >
        {icps.map((icp) => (
          <motion.div
            key={icp.id}
            variants={{
              hidden: { opacity: 0, y: 12 },
              visible: { opacity: 1, y: 0 },
            }}
            className="rounded-2xl border border-emerald-400/30 bg-[#192825] p-5 space-y-3 shadow-[0_14px_36px_rgba(0,0,0,0.38)] hover:border-emerald-400/55 transition-colors"
          >
            <div className="flex items-start justify-between gap-2">
              <h3 className="text-sm font-semibold text-zinc-50">{icp.name}</h3>
              <span className="shrink-0 rounded bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 text-[10px] font-mono text-emerald-300">
                {icp.min_employees}–{icp.max_employees} devs
              </span>
            </div>

            <div className="space-y-1.5 text-xs">
              <div className="flex items-center gap-1.5 text-zinc-400">
                <Users className="h-3.5 w-3.5 text-zinc-500" />
                <span>{icp.target_roles.join(", ")}</span>
              </div>
              <div className="flex items-start gap-1.5 text-zinc-400">
                <Cpu className="h-3.5 w-3.5 shrink-0 mt-0.5 text-zinc-500" />
                <div className="flex flex-wrap gap-1">
                  {icp.required_tech_signals.map((sig) => (
                    <span
                      key={sig}
                      className="rounded bg-zinc-900 border border-zinc-800 px-1.5 py-0.5 text-[10px] font-mono text-zinc-300"
                    >
                      {sig}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div className="pt-2 border-t border-zinc-800/80 space-y-1.5 text-xs">
              <div className="flex items-center gap-1 text-[10px] font-mono uppercase text-emerald-400">
                <Zap className="h-3 w-3" />
                Buying Triggers
              </div>
              <ul className="space-y-1 text-zinc-300">
                {icp.buying_triggers.slice(0, 2).map((trig, i) => (
                  <li key={i} className="leading-snug">
                    • {trig}
                  </li>
                ))}
              </ul>
            </div>

            {icp.instant_disqualifiers.length > 0 && (
              <div className="pt-2 border-t border-zinc-800/80 space-y-1 text-[11px]">
                <div className="flex items-center gap-1 text-[10px] font-mono uppercase text-rose-400">
                  <Layers className="h-3 w-3" />
                  Instant Kill Triggers
                </div>
                <p className="text-rose-200/80">
                  {icp.instant_disqualifiers.slice(0, 2).join(" · ")}
                </p>
              </div>
            )}
          </motion.div>
        ))}
      </motion.div>
    </section>
  );
}
