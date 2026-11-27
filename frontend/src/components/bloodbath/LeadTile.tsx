"use client";

import React from "react";
import { motion } from "framer-motion";
import { CheckCircle2, RotateCcw, Skull } from "lucide-react";
import { useLeadSlayerStore } from "@/store/useLeadSlayerStore";

interface LeadTileProps {
  leadId: string;
  index?: number;
}

export const LeadTile = React.memo(function LeadTile({
  leadId,
  index = 0,
}: LeadTileProps) {
  const lead = useLeadSlayerStore((s) => s.leadsById[leadId]);
  const verdict = useLeadSlayerStore((s) => s.verdictsById[leadId]);
  const phase = useLeadSlayerStore((s) => s.phase);
  const isSelected = useLeadSlayerStore((s) => s.selectedLeadId === leadId);
  const activeFilter = useLeadSlayerStore((s) => s.activeCategoryFilter);
  const setSelectedLeadId = useLeadSlayerStore((s) => s.setSelectedLeadId);

  if (!lead) return null;

  const isMatchesFilter =
    activeFilter === "ALL" ||
    (verdict &&
      ((activeFilter === "SURVIVED" && verdict.survived) ||
        (!verdict.survived && verdict.rejection_category === activeFilter)));

  const status = !verdict
    ? "PENDING"
    : verdict.survived
      ? "SURVIVED"
      : "KILLED";
  const isHuntingScan = status === "PENDING" && phase === "HUNTING";
  const isSlayingQueue = status === "PENDING" && phase === "SLAYING";

  return (
    <motion.button
      type="button"
      onClick={() => setSelectedLeadId(leadId)}
      initial={false}
      animate={{
        scale: status === "SURVIVED" ? [1, 1.04, 1] : 1,
        opacity: !isMatchesFilter ? 0.18 : status === "KILLED" ? 0.68 : 1,
      }}
      transition={{ duration: 0.22 }}
      className={`group relative overflow-hidden rounded-lg border p-2 text-left transition-colors cursor-pointer select-none min-h-[84px] flex flex-col justify-between ${
        isSelected ? "ring-2 ring-sky-400" : ""
      } ${
        status === "PENDING"
          ? isHuntingScan
            ? "border-indigo-500/40 bg-indigo-950/20 hover:border-indigo-400/60"
            : isSlayingQueue
              ? "border-amber-500/35 bg-zinc-900/70 hover:border-zinc-600"
              : "border-zinc-800 bg-zinc-900/50 hover:border-zinc-700"
          : status === "SURVIVED"
            ? "border-emerald-500/75 bg-emerald-950/35 shadow-[0_0_16px_rgba(16,185,129,0.22)] hover:border-emerald-400"
            : "border-rose-500/35 bg-rose-950/20 hover:border-rose-400/60"
      }`}
    >
      {isHuntingScan && (
        <motion.div
          className="pointer-events-none absolute inset-0 bg-gradient-to-r from-transparent via-indigo-400/15 to-transparent"
          animate={{ x: ["-100%", "120%"] }}
          transition={{
            duration: 1.4,
            repeat: Infinity,
            delay: (index % 10) * 0.08 + Math.floor(index / 10) * 0.12,
            ease: "easeInOut",
          }}
        />
      )}

      {status === "KILLED" && (
        <motion.div
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          style={{ originX: 0 }}
          className="pointer-events-none absolute inset-x-0 top-1/2 h-[1.5px] -rotate-12 bg-rose-500/75"
        />
      )}

      <div className="flex items-start justify-between gap-1">
        <div className="min-w-0">
          <div className="truncate text-[11px] font-semibold text-zinc-100">
            {lead.company}
          </div>
          <div className="truncate text-[10px] text-zinc-400">
            {lead.full_name}
          </div>
        </div>

        {status === "PENDING" ? (
          <span
            className={`mt-0.5 h-2 w-2 shrink-0 rounded-full animate-pulse ${
              isHuntingScan
                ? "bg-indigo-400 shadow-[0_0_8px_#818cf8]"
                : isSlayingQueue
                  ? "bg-amber-400"
                  : "bg-zinc-600"
            }`}
          />
        ) : status === "SURVIVED" ? (
          verdict?.resurrected_by_user ? (
            <RotateCcw className="h-3.5 w-3.5 shrink-0 text-amber-300" />
          ) : (
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
          )
        ) : (
          <Skull className="h-3.5 w-3.5 shrink-0 text-rose-400/80" />
        )}
      </div>

      <div className="mt-1.5 flex items-center justify-between gap-1">
        {!verdict ? (
          <span
            className={`truncate text-[9px] font-mono ${
              isHuntingScan
                ? "text-indigo-300"
                : isSlayingQueue
                  ? "text-amber-300/80"
                  : "text-zinc-500"
            }`}
          >
            {isHuntingScan ? "VECTOR SCAN..." : lead.role}
          </span>
        ) : (
          <>
            <span
              className={`truncate rounded px-1 py-0.5 text-[9px] font-mono leading-none ${
                verdict.survived
                  ? verdict.resurrected_by_user
                    ? "bg-amber-500/20 text-amber-200"
                    : "bg-emerald-500/20 text-emerald-300"
                  : "bg-rose-500/20 text-rose-300"
              }`}
            >
              {verdict.headline_tag}
            </span>
            <span
              className={`shrink-0 text-[9px] font-mono font-semibold ${
                verdict.survived ? "text-emerald-300" : "text-zinc-500"
              }`}
            >
              {verdict.qualification_score}
            </span>
          </>
        )}
      </div>
    </motion.button>
  );
});
