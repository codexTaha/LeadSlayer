"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Download, Loader2, Send, ShieldAlert } from "lucide-react";
import { dispatchEmails, fetchHarveyStatus, getExportUrl } from "@/lib/api";
import { useLeadSlayerStore } from "@/store/useLeadSlayerStore";
import type {
  DeliveryMode,
  DispatchResponse,
  HarveyStatusResponse,
} from "@/types/contracts";

export function DispatchExportBar() {
  const runId = useLeadSlayerStore((s) => s.runId);
  const phase = useLeadSlayerStore((s) => s.phase);
  const emailsById = useLeadSlayerStore((s) => s.emailsById);
  const markDispatched = useLeadSlayerStore((s) => s.markDispatched);
  const setError = useLeadSlayerStore((s) => s.setError);

  const [isSending, setIsSending] = useState(false);
  const [deliveryMode, setDeliveryMode] = useState<DeliveryMode>("SANDBOX");
  const [harveyStatus, setHarveyStatus] = useState<HarveyStatusResponse | null>(
    null
  );
  const [lastResult, setLastResult] = useState<DispatchResponse | null>(null);

  useEffect(() => {
    void fetchHarveyStatus()
      .then((st) => setHarveyStatus(st))
      .catch(() => {});
  }, []);

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
      const res = await dispatchEmails(runId, targetIds, deliveryMode);
      setLastResult(res);
      const sentIds = res.receipts
        .filter((r) => r.status === "SENT")
        .map((r) => r.lead_id);
      if (sentIds.length > 0) {
        markDispatched(sentIds);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to dispatch emails."
      );
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="sticky bottom-4 z-20 rounded-2xl border border-zinc-800 bg-[#0A0D12]/95 p-4 shadow-2xl backdrop-blur-md space-y-2.5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          {allSent || phase === "DISPATCHED" ? (
            <div className="flex items-center gap-2 text-sm font-semibold text-emerald-300">
              <CheckCircle2 className="h-5 w-5 text-emerald-400" />
              Campaign Dispatched via{" "}
              {lastResult?.delivery_mode || deliveryMode} —{" "}
              {lastResult?.dispatched_count ?? approvedDrafts.length} Sent
              {(lastResult?.blocked_count ?? 0) > 0 &&
                ` · ${lastResult?.blocked_count} Blocked by Harvey Gate`}
            </div>
          ) : (
            <div className="text-sm text-zinc-200">
              <span className="font-mono font-bold text-emerald-400">
                {approvedDrafts.length}
              </span>{" "}
              of {allDrafts.length} Survivor Emails Approved for Harvey Dispatch
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2 text-[11px] font-mono text-zinc-400">
            <span className="text-emerald-400">Harvey Send Gate Active</span>
            <span>·</span>
            <span>
              SMTP: {harveyStatus?.smtp_configured ? "Armed" : "Add SMTP_* in .env"}
            </span>
            <span>·</span>
            <span>
              Gmail OAuth: {harveyStatus?.gmail_configured ? "Armed" : "Not linked"}
            </span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <select
            value={deliveryMode}
            disabled={isSending || allSent}
            onChange={(e) => setDeliveryMode(e.target.value as DeliveryMode)}
            aria-label="Harvey Delivery Transport"
            className="rounded-xl border border-zinc-700 bg-zinc-900 px-3 py-2.5 text-xs font-mono text-zinc-200 focus:border-emerald-500 focus:outline-none disabled:opacity-50"
          >
            <option value="SANDBOX">Harvey Safe Sandbox ($0 Demo)</option>
            <option value="HARVEY_SMTP">
              Harvey Live SMTP {harveyStatus?.smtp_configured ? "(Armed)" : "(Needs .env)"}
            </option>
            <option value="HARVEY_GMAIL">
              Harvey Live Gmail {harveyStatus?.gmail_configured ? "(Armed)" : "(Needs Auth)"}
            </option>
          </select>

          <a
            href={getExportUrl(runId, "csv")}
            download
            className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-900 px-3.5 py-2.5 text-xs font-medium text-zinc-200 hover:border-zinc-500 hover:bg-zinc-800"
          >
            <Download className="h-3.5 w-3.5 text-emerald-400" />
            Export (.CSV)
          </a>

          <a
            href={getExportUrl(runId, "json")}
            download
            className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-900 px-3.5 py-2.5 text-xs font-medium text-zinc-200 hover:border-zinc-500 hover:bg-zinc-800"
          >
            <Download className="h-3.5 w-3.5 text-rose-400" />
            Kill Audit (.JSON)
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
                ? "Sending via Harvey..."
                : deliveryMode === "SANDBOX"
                  ? `Approve & Simulate (${approvedDrafts.length})`
                  : `Send Live via Harvey (${approvedDrafts.length})`}
          </button>
        </div>
      </div>

      {lastResult && lastResult.receipts.some((r) => r.status !== "SENT") && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-950/25 px-3 py-2 text-xs text-amber-200 flex items-start gap-2">
          <ShieldAlert className="h-4 w-4 shrink-0 text-amber-400 mt-0.5" />
          <div className="space-y-0.5 font-mono text-[11px]">
            {lastResult.receipts
              .filter((r) => r.status !== "SENT")
              .slice(0, 3)
              .map((r) => (
                <div key={r.lead_id}>
                  {r.recipient_email}: {r.status} —{" "}
                  {(r.gate_reasons && r.gate_reasons.join(", ")) || r.error}
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
