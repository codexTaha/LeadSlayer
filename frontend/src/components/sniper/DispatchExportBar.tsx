"use client";

import { useState } from "react";
import { CheckCircle2, Download, Loader2, Send } from "lucide-react";
import { dispatchEmails, getExportUrl } from "@/lib/api";
import { useLeadSlayerStore } from "@/store/useLeadSlayerStore";

export function DispatchExportBar() {
  const runId = useLeadSlayerStore((s) => s.runId);
  const phase = useLeadSlayerStore((s) => s.phase);
  const emailsById = useLeadSlayerStore((s) => s.emailsById);
  const markDispatched = useLeadSlayerStore((s) => s.markDispatched);
  const setError = useLeadSlayerStore((s) => s.setError);

  const [isSending, setIsSending] = useState(false);

  const allDrafts = Object.values(emailsById);
  if (allDrafts.length === 0 || !runId) return null;

  const approvedDrafts = allDrafts.filter((d) => d.approved);
  const allSent = allDrafts.every((d) => d.status === "SENT");

  const handleDispatch = async () => {
    if (approvedDrafts.length === 0) return;
    setIsSending(true);
    setError(null);
    try {
      const targetIds = approvedDrafts.map((d) => d.lead_id);
      await dispatchEmails(runId, targetIds);
      markDispatched(targetIds);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to dispatch emails."
      );
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="sticky bottom-4 z-20 rounded-2xl border border-zinc-800 bg-[#0A0D12]/95 p-4 shadow-2xl backdrop-blur-md">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          {allSent || phase === "DISPATCHED" ? (
            <div className="flex items-center gap-2 text-sm font-semibold text-emerald-300">
              <CheckCircle2 className="h-5 w-5 text-emerald-400" />
              Campaign Dispatched — {approvedDrafts.length} Hyper-Personalized
              Emails Sent (Zero Spam)
            </div>
          ) : (
            <div className="text-sm text-zinc-200">
              <span className="font-mono font-bold text-emerald-400">
                {approvedDrafts.length}
              </span>{" "}
              of {allDrafts.length} Survivor Emails Approved for Outreach
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <a
            href={getExportUrl(runId, "csv")}
            download
            className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-900 px-3.5 py-2.5 text-xs font-medium text-zinc-200 hover:border-zinc-500 hover:bg-zinc-800"
          >
            <Download className="h-3.5 w-3.5 text-emerald-400" />
            Export Survivors (.CSV)
          </a>

          <a
            href={getExportUrl(runId, "json")}
            download
            className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-900 px-3.5 py-2.5 text-xs font-medium text-zinc-200 hover:border-zinc-500 hover:bg-zinc-800"
          >
            <Download className="h-3.5 w-3.5 text-rose-400" />
            Export Kill Audit (.JSON)
          </a>

          <button
            type="button"
            disabled={isSending || approvedDrafts.length === 0 || allSent}
            onClick={handleDispatch}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-emerald-500 px-5 py-2.5 text-sm font-semibold text-white shadow-[0_0_24px_rgba(16,185,129,0.3)] hover:from-emerald-500 hover:to-emerald-400 transition cursor-pointer disabled:opacity-50 disabled:shadow-none disabled:cursor-not-allowed"
          >
            {isSending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : allSent ? (
              <CheckCircle2 className="h-4 w-4" />
            ) : (
              <Send className="h-4 w-4" />
            )}
            {allSent
              ? "Dispatched"
              : isSending
                ? "Dispatching..."
                : `Approve All & Send (${approvedDrafts.length} Emails)`}
          </button>
        </div>
      </div>
    </div>
  );
}
