"use client";

import { useEffect, useState } from "react";
import {
  CheckCircle2,
  Clock,
  Download,
  Loader2,
  Mail,
  Send,
  ShieldAlert,
  Unplug,
  X,
} from "lucide-react";
import {
  connectSmtpAccount,
  disconnectMailAccount,
  dispatchEmails,
  fetchMailStatus,
  getExportUrl,
  getGoogleOAuthStartUrl,
} from "@/lib/api";
import { useLeadSlayerStore } from "@/store/useLeadSlayerStore";
import type {
  DeliveryMode,
  DispatchResponse,
  MailStatusResponse,
} from "@/types/contracts";

export function DispatchExportBar() {
  const runId = useLeadSlayerStore((s) => s.runId);
  const phase = useLeadSlayerStore((s) => s.phase);
  const emailsById = useLeadSlayerStore((s) => s.emailsById);
  const telemetry = useLeadSlayerStore((s) => s.telemetry);
  const markDispatched = useLeadSlayerStore((s) => s.markDispatched);
  const setError = useLeadSlayerStore((s) => s.setError);

  const [isSending, setIsSending] = useState(false);
  const [deliveryMode, setDeliveryMode] = useState<DeliveryMode>("SANDBOX");
  const [mailStatus, setMailStatus] = useState<MailStatusResponse | null>(null);
  const [lastResult, setLastResult] = useState<DispatchResponse | null>(null);

  const [showMailModal, setShowMailModal] = useState(false);
  const [smtpEmail, setSmtpEmail] = useState("");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [smtpHost, setSmtpHost] = useState("smtp.gmail.com");
  const [smtpPort, setSmtpPort] = useState(587);
  const [senderName, setSenderName] = useState("LeadSlayer");
  const [postalAddress, setPostalAddress] = useState("");
  const [mailModalBusy, setMailModalBusy] = useState(false);
  const [mailModalError, setMailModalError] = useState<string | null>(null);

  const refreshMailStatus = () => {
    void fetchMailStatus()
      .then((st) => {
        setMailStatus(st);
        if (st.smtp_configured && deliveryMode === "SANDBOX") {
          setDeliveryMode("SMTP");
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    void fetchMailStatus()
      .then((st) => setMailStatus(st))
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

  const handleConnectSmtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setMailModalBusy(true);
    setMailModalError(null);
    try {
      const updated = await connectSmtpAccount({
        email: smtpEmail.trim(),
        password: smtpPassword,
        smtp_host: smtpHost.trim(),
        smtp_port: Number(smtpPort) || 587,
        sender_name: senderName.trim() || "LeadSlayer",
        postal_address: postalAddress.trim(),
        verify_connection: true,
      });
      setMailStatus(updated);
      setDeliveryMode("SMTP");
      setSmtpPassword("");
      setShowMailModal(false);
    } catch (err) {
      setMailModalError(
        err instanceof Error ? err.message : "SMTP authentication failed."
      );
    } finally {
      setMailModalBusy(false);
    }
  };

  const handleDisconnect = async () => {
    setMailModalBusy(true);
    try {
      const updated = await disconnectMailAccount();
      setMailStatus(updated);
      setDeliveryMode("SANDBOX");
      setShowMailModal(false);
    } finally {
      setMailModalBusy(false);
    }
  };

  return (
    <>
      <div className="sticky bottom-4 z-30 rounded-2xl border-2 border-emerald-400/75 bg-[#10241E] p-4 sm:p-5 shadow-[0_-10px_42px_rgba(0,0,0,0.85),0_0_32px_rgba(16,185,129,0.22)] ring-1 ring-emerald-300/20 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1.5">
            {allSent || phase === "DISPATCHED" ? (
              <div className="flex items-center gap-2 text-base font-bold text-emerald-200">
                <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0" />
                Campaign Dispatched via{" "}
                {lastResult?.delivery_mode || deliveryMode} —{" "}
                {lastResult?.dispatched_count ?? approvedDrafts.length} Sent
                {(lastResult?.blocked_count ?? 0) > 0 &&
                  ` · ${lastResult?.blocked_count} Blocked by Deliverability Gate`}
              </div>
            ) : (
              <div className="flex flex-wrap items-center gap-2 text-base font-semibold text-white">
                <span className="inline-flex items-center rounded-md border border-emerald-400/60 bg-emerald-500/25 px-2 py-0.5 font-mono text-sm font-bold text-emerald-200">
                  {approvedDrafts.length} / {allDrafts.length}
                </span>
                <span>Survivor Emails Approved for Dispatch</span>
              </div>
            )}

            <div className="flex flex-wrap items-center gap-2 text-xs font-mono text-stone-200">
              <span className="inline-flex items-center gap-1.5 text-emerald-300 font-semibold">
                <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" />
                Deliverability Gate Active
              </span>
              <span className="text-stone-500">·</span>
              <span>
                SMTP:{" "}
                <span className="text-stone-100">
                  {mailStatus?.smtp_configured
                    ? `Connected (${mailStatus.smtp_sender || "Ready"})`
                    : "Not connected"}
                </span>
              </span>
              <span className="text-stone-500">·</span>
              <span>
                Gmail OAuth:{" "}
                <span className="text-stone-100">
                  {mailStatus?.gmail_configured ? "Connected" : "Not linked"}
                </span>
              </span>
              {telemetry && (
                <>
                  <span className="text-stone-500">·</span>
                  <span className="inline-flex items-center gap-1 font-semibold text-amber-300">
                    <Clock className="h-3.5 w-3.5" />
                    {telemetry.estimated_saved_spam_hours} hrs saved
                  </span>
                </>
              )}
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <button
              type="button"
              onClick={() => {
                setMailModalError(null);
                setShowMailModal(true);
              }}
              className={`inline-flex items-center gap-1.5 rounded-xl border px-3.5 py-2.5 text-xs font-semibold transition cursor-pointer ${
                mailStatus?.smtp_configured || mailStatus?.gmail_configured
                  ? "border-emerald-400/60 bg-emerald-500/20 text-emerald-100 hover:bg-emerald-500/30"
                  : "border-indigo-400/60 bg-indigo-500/20 text-indigo-100 hover:bg-indigo-500/30"
              }`}
            >
              <Mail className="h-3.5 w-3.5" />
              {mailStatus?.smtp_configured || mailStatus?.gmail_configured
                ? "Mailbox Connected"
                : "Connect Email"}
            </button>

            <select
              value={deliveryMode}
              disabled={isSending || allSent}
              onChange={(e) => setDeliveryMode(e.target.value as DeliveryMode)}
              aria-label="Email Delivery Transport"
              className="rounded-xl border border-stone-500/70 bg-[#182E28] px-3 py-2.5 text-xs font-mono font-medium text-stone-100 focus:border-emerald-400 focus:outline-none disabled:opacity-50"
            >
              <option value="SANDBOX">Safe Sandbox ($0 Demo)</option>
              <option value="SMTP">
                Live SMTP {mailStatus?.smtp_configured ? "(Ready)" : "(Connect Email)"}
              </option>
              <option value="GMAIL_OAUTH">
                Live Gmail OAuth {mailStatus?.gmail_configured ? "(Ready)" : "(Link Google)"}
              </option>
            </select>

            <a
              href={getExportUrl(runId, "csv")}
              download
              className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-400/65 bg-emerald-500/20 px-3.5 py-2.5 text-xs font-semibold text-emerald-100 hover:border-emerald-300 hover:bg-emerald-500/30 transition"
            >
              <Download className="h-3.5 w-3.5 text-emerald-300" />
              Download Verified Leads (.CSV)
            </a>

            <a
              href={getExportUrl(runId, "json")}
              download
              className="inline-flex items-center gap-1.5 rounded-xl border border-rose-400/50 bg-rose-500/15 px-3.5 py-2.5 text-xs font-semibold text-rose-100 hover:border-rose-300 hover:bg-rose-500/25 transition"
            >
              <Download className="h-3.5 w-3.5 text-rose-300" />
              Kill Audit (.JSON)
            </a>

            <button
              type="button"
              disabled={isSending || approvedDrafts.length === 0 || allSent}
              onClick={handleDispatch}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-400 px-5 py-2.5 text-sm font-bold text-zinc-950 shadow-[0_0_26px_rgba(16,185,129,0.45)] hover:from-emerald-400 hover:to-teal-300 transition cursor-pointer disabled:opacity-50 disabled:shadow-none disabled:cursor-not-allowed"
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
                  ? "Sending..."
                  : deliveryMode === "SANDBOX"
                    ? `Approve & Simulate (${approvedDrafts.length})`
                    : `Send Live (${approvedDrafts.length})`}
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

      {showMailModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-zinc-800 bg-[#0B0E14] p-5 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
              <div className="flex items-center gap-2">
                <Mail className="h-4 w-4 text-indigo-400" />
                <h3 className="text-sm font-bold text-zinc-100">
                  Connect Sender Mailbox
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowMailModal(false)}
                className="rounded-lg p-1 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 cursor-pointer"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => {
                  setSmtpHost("smtp.gmail.com");
                  setSmtpPort(587);
                }}
                className={`rounded-lg border px-2.5 py-1 text-[11px] font-mono cursor-pointer ${
                  smtpHost === "smtp.gmail.com"
                    ? "border-indigo-400/60 bg-indigo-500/20 text-indigo-200"
                    : "border-zinc-800 bg-zinc-900 text-zinc-400"
                }`}
              >
                Gmail (App Password)
              </button>
              <button
                type="button"
                onClick={() => {
                  setSmtpHost("smtp.office365.com");
                  setSmtpPort(587);
                }}
                className={`rounded-lg border px-2.5 py-1 text-[11px] font-mono cursor-pointer ${
                  smtpHost === "smtp.office365.com"
                    ? "border-indigo-400/60 bg-indigo-500/20 text-indigo-200"
                    : "border-zinc-800 bg-zinc-900 text-zinc-400"
                }`}
              >
                Outlook / 365
              </button>
              <button
                type="button"
                onClick={() => {
                  setSmtpHost("");
                  setSmtpPort(587);
                }}
                className={`rounded-lg border px-2.5 py-1 text-[11px] font-mono cursor-pointer ${
                  smtpHost !== "smtp.gmail.com" &&
                  smtpHost !== "smtp.office365.com"
                    ? "border-indigo-400/60 bg-indigo-500/20 text-indigo-200"
                    : "border-zinc-800 bg-zinc-900 text-zinc-400"
                }`}
              >
                Custom SMTP
              </button>
            </div>

            <form onSubmit={handleConnectSmtp} className="space-y-3">
              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-[10px] font-mono uppercase text-zinc-400 mb-1">
                    Sender Name
                  </label>
                  <input
                    type="text"
                    required
                    value={senderName}
                    onChange={(e) => setSenderName(e.target.value)}
                    placeholder="Alex from Orbix"
                    className="w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-zinc-100 focus:border-indigo-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-mono uppercase text-zinc-400 mb-1">
                    Email Address
                  </label>
                  <input
                    type="email"
                    required
                    value={smtpEmail}
                    onChange={(e) => setSmtpEmail(e.target.value)}
                    placeholder="you@gmail.com"
                    className="w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-zinc-100 focus:border-indigo-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-mono uppercase text-zinc-400 mb-1">
                  Password / Gmail 16-Char App Password
                </label>
                <input
                  type="password"
                  required
                  value={smtpPassword}
                  onChange={(e) => setSmtpPassword(e.target.value)}
                  placeholder="••••••••••••••••"
                  className="w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-zinc-100 focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-3 gap-2.5">
                <div className="col-span-2">
                  <label className="block text-[10px] font-mono uppercase text-zinc-400 mb-1">
                    SMTP Host
                  </label>
                  <input
                    type="text"
                    required
                    value={smtpHost}
                    onChange={(e) => setSmtpHost(e.target.value)}
                    placeholder="smtp.gmail.com"
                    className="w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-zinc-100 focus:border-indigo-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-mono uppercase text-zinc-400 mb-1">
                    Port
                  </label>
                  <input
                    type="number"
                    required
                    value={smtpPort}
                    onChange={(e) => setSmtpPort(Number(e.target.value))}
                    className="w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-zinc-100 focus:border-indigo-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-mono uppercase text-zinc-400 mb-1">
                  Postal Footer (Optional CAN-SPAM)
                </label>
                <input
                  type="text"
                  value={postalAddress}
                  onChange={(e) => setPostalAddress(e.target.value)}
                  placeholder="Acme Inc, 123 Main St, Austin TX"
                  className="w-full rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-zinc-100 focus:border-indigo-500 focus:outline-none"
                />
              </div>

              {mailModalError && (
                <div className="rounded-lg border border-rose-500/40 bg-rose-950/30 px-3 py-2 text-[11px] text-rose-200">
                  {mailModalError}
                </div>
              )}

              <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
                {(mailStatus?.smtp_configured || mailStatus?.gmail_configured) && (
                  <button
                    type="button"
                    disabled={mailModalBusy}
                    onClick={handleDisconnect}
                    className="inline-flex items-center gap-1 rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-300 hover:bg-rose-500/20 cursor-pointer"
                  >
                    <Unplug className="h-3.5 w-3.5" />
                    Disconnect
                  </button>
                )}

                <div className="flex items-center gap-2 ml-auto">
                  {mailStatus?.gmail_oauth_available && (
                    <a
                      href={getGoogleOAuthStartUrl()}
                      onClick={() => refreshMailStatus()}
                      className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs text-zinc-200 hover:bg-zinc-800"
                    >
                      Google OAuth
                    </a>
                  )}
                  <button
                    type="submit"
                    disabled={mailModalBusy}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500 cursor-pointer disabled:opacity-50"
                  >
                    {mailModalBusy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                    Verify &amp; Connect
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
