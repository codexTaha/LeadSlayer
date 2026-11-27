"use client";

import { motion } from "framer-motion";
import { Check, CheckCircle2, MailCheck, RotateCcw } from "lucide-react";
import { EvidenceHighlightedBody } from "@/components/sniper/EvidenceHighlightedBody";
import { useLeadSlayerStore } from "@/store/useLeadSlayerStore";
import type { EmailDraft } from "@/types/contracts";

interface SniperEmailCardProps {
  draft: EmailDraft;
}

export function SniperEmailCard({ draft }: SniperEmailCardProps) {
  const lead = useLeadSlayerStore((s) => s.leadsById[draft.lead_id]);
  const verdict = useLeadSlayerStore((s) => s.verdictsById[draft.lead_id]);
  const toggleEmailApproval = useLeadSlayerStore((s) => s.toggleEmailApproval);

  const isSent = draft.status === "SENT";

  return (
    <motion.article
      initial={{ opacity: 0, y: 16, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className={`rounded-2xl border p-5 space-y-4 transition-colors ${
        isSent
          ? "border-emerald-400/60 bg-emerald-950/20"
          : draft.approved
            ? "border-emerald-500/45 bg-zinc-950/90 shadow-[0_0_24px_rgba(16,185,129,0.1)]"
            : "border-zinc-800 bg-zinc-950/60 opacity-75"
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-zinc-800/80 pb-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold text-zinc-50">
              {draft.recipient_name}
            </h3>
            {verdict?.resurrected_by_user && (
              <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/40 bg-amber-500/15 px-2 py-0.5 text-[10px] font-mono text-amber-200">
                <RotateCcw className="h-3 w-3" />
                RESURRECTED
              </span>
            )}
            {isSent && (
              <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/50 bg-emerald-500/20 px-2 py-0.5 text-[10px] font-mono text-emerald-200">
                <MailCheck className="h-3 w-3" />
                SENT
              </span>
            )}
          </div>
          <p className="text-xs text-zinc-400">
            {lead?.role ? `${lead.role} @ ` : ""}
            {draft.company} ·{" "}
            <span className="font-mono text-zinc-500">
              {draft.recipient_email}
            </span>
            {lead?.source_channel && lead.source_channel !== "CSV" && (
              <span className="ml-2 rounded border border-indigo-500/35 bg-indigo-500/10 px-1.5 py-0.2 text-[10px] font-mono text-indigo-300">
                {lead.source_channel}
              </span>
            )}
            {lead?.email_status && lead.email_status !== "unknown" && (
              <span className="ml-1.5 rounded border border-zinc-700 bg-zinc-900 px-1.5 py-0.2 text-[10px] font-mono text-zinc-300">
                {lead.email_status}
                {lead.mx_provider ? ` · MX:${lead.mx_provider}` : ""}
              </span>
            )}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-[11px] font-mono text-emerald-300">
            {verdict?.qualification_score ?? draft.personalization_score}/100 Fit
          </span>

          <button
            type="button"
            disabled={isSent}
            onClick={() => toggleEmailApproval(draft.lead_id)}
            className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition cursor-pointer disabled:cursor-default ${
              draft.approved
                ? "border-emerald-500/50 bg-emerald-500/20 text-emerald-200"
                : "border-zinc-700 bg-zinc-900 text-zinc-400 hover:border-zinc-500"
            }`}
          >
            {isSent ? (
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-300" />
            ) : (
              <Check className="h-3.5 w-3.5" />
            )}
            {isSent ? "Dispatched" : draft.approved ? "Approved" : "Skipped"}
          </button>
        </div>
      </div>

      <div className="rounded-lg border border-zinc-800/80 bg-zinc-900/50 px-3 py-2 text-xs">
        <span className="font-mono text-zinc-500 mr-2">SUBJECT:</span>
        <span className="font-semibold text-zinc-100">{draft.subject}</span>
      </div>

      <EvidenceHighlightedBody draft={draft} verdict={verdict} />
    </motion.article>
  );
}
