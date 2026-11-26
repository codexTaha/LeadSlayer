"use client";

import { motion } from "framer-motion";
import { Lock, ShieldBan } from "lucide-react";
import { useLeadSlayerStore } from "@/store/useLeadSlayerStore";

export function AntiICPLockStrip() {
  const audit = useLeadSlayerStore((s) => s.marketAudit);
  const phase = useLeadSlayerStore((s) => s.phase);

  if (!audit || audit.anti_icp_red_flags.length === 0) return null;

  return (
    <motion.section
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
      className="rounded-xl border border-rose-500/40 bg-gradient-to-r from-rose-950/40 via-zinc-950 to-rose-950/30 p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 mb-2.5">
        <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-rose-300">
          <ShieldBan className="h-4 w-4 text-rose-400" />
          Anti-ICP Kill Rules Locked Into Slayer Agent
        </div>
        <span className="inline-flex items-center gap-1 rounded-full border border-rose-500/40 bg-rose-500/15 px-2.5 py-0.5 text-[10px] font-mono text-rose-200">
          <Lock className="h-3 w-3" />
          {phase === "AUDITING" ? "CALIBRATING" : "ARMED FOR BLOODBATH"}
        </span>
      </div>

      <div className="flex flex-wrap gap-2">
        {audit.anti_icp_red_flags.map((rule, idx) => (
          <motion.span
            key={idx}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: idx * 0.06 }}
            className="inline-flex items-center gap-1.5 rounded-lg border border-rose-500/30 bg-rose-500/10 px-2.5 py-1 text-xs text-rose-200"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
            {rule}
          </motion.span>
        ))}
      </div>
    </motion.section>
  );
}
