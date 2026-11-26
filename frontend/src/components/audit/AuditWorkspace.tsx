"use client";

import { useRef, useState } from "react";
import {
  ArrowRight,
  FileSpreadsheet,
  Loader2,
  Play,
  Sparkles,
  Upload,
} from "lucide-react";
import { AntiICPLockStrip } from "@/components/audit/AntiICPLockStrip";
import { ICPCardsGrid } from "@/components/audit/ICPCardsGrid";
import { MarketAuditCard } from "@/components/audit/MarketAuditCard";
import { SlayingLevelSelector } from "@/components/audit/SlayingLevelSelector";
import { fetchDemoPreset, parseCsvLeads } from "@/lib/api";
import { useLeadSlayerStore } from "@/store/useLeadSlayerStore";

interface AuditWorkspaceProps {
  onLaunch: () => void;
}

export function AuditWorkspace({ onLaunch }: AuditWorkspaceProps) {
  const phase = useLeadSlayerStore((s) => s.phase);
  const startupInput = useLeadSlayerStore((s) => s.startupInput);
  const leadOrder = useLeadSlayerStore((s) => s.leadOrder);
  const isLoadingPreset = useLeadSlayerStore((s) => s.isLoadingPreset);
  const isStartingRun = useLeadSlayerStore((s) => s.isStartingRun);
  const setIsLoadingPreset = useLeadSlayerStore((s) => s.setIsLoadingPreset);
  const setPresetData = useLeadSlayerStore((s) => s.setPresetData);
  const setCustomLeads = useLeadSlayerStore((s) => s.setCustomLeads);
  const updateStartupInput = useLeadSlayerStore((s) => s.updateStartupInput);
  const setError = useLeadSlayerStore((s) => s.setError);
  const setActiveViewTab = useLeadSlayerStore((s) => s.setActiveViewTab);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [csvLabel, setCsvLabel] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const isLocked = phase !== "IDLE" && phase !== "ERROR";

  const handleLoadSample = async () => {
    setIsLoadingPreset(true);
    setError(null);
    try {
      const preset = await fetchDemoPreset();
      setPresetData(preset.startup, preset.leads);
      setCsvLabel("50-Lead Adversarial Swarm Preset Ready");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to load 50-lead preset."
      );
    } finally {
      setIsLoadingPreset(false);
    }
  };

  const handleCsvFile = async (file: File) => {
    setError(null);
    try {
      const parsed = await parseCsvLeads(file);
      setCustomLeads(parsed.leads);
      setCsvLabel(`${parsed.count} Leads Loaded from ${file.name}`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to parse uploaded CSV."
      );
    }
  };

  const canLaunch =
    !isLocked &&
    !isStartingRun &&
    startupInput.product_name.trim().length >= 2 &&
    startupInput.description.trim().length >= 20 &&
    startupInput.founder_assumptions.trim().length >= 5;

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-zinc-800 bg-zinc-950/90 p-5 sm:p-6 shadow-2xl space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800/80 pb-4">
          <div>
            <span className="text-[11px] font-mono uppercase tracking-wider text-rose-400">
              Act 1 · Target Product &amp; Swarm Configuration
            </span>
            <h1 className="text-xl font-bold tracking-tight text-zinc-50 mt-0.5">
              Define Your Product. Let LeadSlayer Slaughter the Noise.
            </h1>
          </div>

          <button
            type="button"
            disabled={isLocked || isLoadingPreset}
            onClick={handleLoadSample}
            className="inline-flex items-center gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 px-3.5 py-2 text-xs font-semibold text-amber-200 hover:bg-amber-500/20 transition cursor-pointer disabled:opacity-50"
          >
            {isLoadingPreset ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4 text-amber-400" />
            )}
            Load KubeGuard AI + 50-Lead Swarm
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          <div className="lg:col-span-8 space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-mono uppercase tracking-wider text-zinc-400 mb-1.5">
                  Startup / Product Name
                </label>
                <input
                  type="text"
                  disabled={isLocked}
                  value={startupInput.product_name}
                  onChange={(e) =>
                    updateStartupInput({ product_name: e.target.value })
                  }
                  placeholder="e.g. KubeGuard AI"
                  className="w-full rounded-lg border border-zinc-800 bg-zinc-900/80 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-rose-500/60 focus:outline-none disabled:opacity-60"
                />
              </div>
              <div>
                <label className="block text-xs font-mono uppercase tracking-wider text-zinc-400 mb-1.5">
                  Product Website URL (Optional Live Read)
                </label>
                <input
                  type="text"
                  disabled={isLocked}
                  value={startupInput.product_url ?? ""}
                  onChange={(e) =>
                    updateStartupInput({ product_url: e.target.value })
                  }
                  placeholder="https://kubeguard.ai"
                  className="w-full rounded-lg border border-zinc-800 bg-zinc-900/80 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-rose-500/60 focus:outline-none disabled:opacity-60"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-mono uppercase tracking-wider text-zinc-400 mb-1.5">
                Product Description &amp; Technical Edge
              </label>
              <textarea
                rows={3}
                disabled={isLocked}
                value={startupInput.description}
                onChange={(e) =>
                  updateStartupInput({ description: e.target.value })
                }
                placeholder="Describe what your product builds, technical stack fit, and core ROI..."
                className="w-full rounded-lg border border-zinc-800 bg-zinc-900/80 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-rose-500/60 focus:outline-none disabled:opacity-60"
              />
            </div>

            <div>
              <label className="block text-xs font-mono uppercase tracking-wider text-zinc-400 mb-1.5">
                Founder&apos;s Market Assumptions (What Auditor Will Challenge)
              </label>
              <textarea
                rows={2}
                disabled={isLocked}
                value={startupInput.founder_assumptions}
                onChange={(e) =>
                  updateStartupInput({ founder_assumptions: e.target.value })
                }
                placeholder="e.g. Any tech startup running cloud servers with a CTO needs us..."
                className="w-full rounded-lg border border-zinc-800 bg-zinc-900/80 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-600 focus:border-rose-500/60 focus:outline-none disabled:opacity-60"
              />
            </div>
          </div>

          <div className="lg:col-span-4 flex flex-col justify-between gap-4">
            <div
              onDragOver={(e) => {
                e.preventDefault();
                if (!isLocked) setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDragging(false);
                const file = e.dataTransfer.files[0];
                if (file && !isLocked) void handleCsvFile(file);
              }}
              onClick={() => !isLocked && fileInputRef.current?.click()}
              className={`flex-1 flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-5 text-center transition cursor-pointer ${
                isDragging
                  ? "border-rose-400 bg-rose-500/10"
                  : "border-zinc-800 bg-zinc-900/40 hover:border-zinc-600"
              } ${isLocked ? "opacity-50 cursor-not-allowed" : ""}`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void handleCsvFile(file);
                }}
              />
              {leadOrder.length > 0 ? (
                <FileSpreadsheet className="h-8 w-8 text-emerald-400 mb-2" />
              ) : (
                <Upload className="h-8 w-8 text-zinc-500 mb-2" />
              )}
              <div className="text-sm font-medium text-zinc-100">
                {leadOrder.length > 0
                  ? `${leadOrder.length} Leads Armed & Ready`
                  : "Drop Lead List CSV"}
              </div>
              <p className="mt-1 text-xs text-zinc-400">
                {csvLabel ||
                  "Supports Apollo / Sales Nav exports or click to upload custom .csv"}
              </p>
            </div>

            <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-3 text-xs text-zinc-400 space-y-1">
              <div className="font-mono text-[10px] uppercase text-zinc-500">
                Strict 3-Model ADK Routing
              </div>
              <div className="flex justify-between">
                <span>Auditor &amp; Sniper</span>
                <span className="font-mono text-indigo-300">gemini-4-hydrogen</span>
              </div>
              <div className="flex justify-between">
                <span>Hunter &amp; Slayer</span>
                <span className="font-mono text-rose-300">gemini-3.5-flash-lite</span>
              </div>
              <div className="flex justify-between">
                <span>Vector Memory</span>
                <span className="font-mono text-emerald-300">gemini-embedding-2</span>
              </div>
            </div>
          </div>
        </div>

        <SlayingLevelSelector disabled={isLocked} />

        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-zinc-800/80">
          <div className="text-xs text-zinc-500 font-mono">
            {phase === "IDLE"
              ? "Ready for autonomous 5-step execution"
              : `Pipeline active: ${phase}`}
          </div>

          <div className="flex items-center gap-3">
            {phase !== "IDLE" && phase !== "ERROR" && (
              <button
                type="button"
                onClick={() => setActiveViewTab("BLOODBATH")}
                className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-2.5 text-xs font-medium text-zinc-200 hover:bg-zinc-800 cursor-pointer"
              >
                Jump to Bloodbath Matrix
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            )}

            <button
              type="button"
              disabled={!canLaunch}
              onClick={onLaunch}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-rose-600 to-rose-500 px-6 py-2.5 text-sm font-semibold text-white shadow-[0_0_25px_rgba(244,63,94,0.35)] transition hover:from-rose-500 hover:to-rose-400 cursor-pointer disabled:opacity-45 disabled:shadow-none disabled:cursor-not-allowed"
            >
              {isStartingRun ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4 fill-current" />
              )}
              {isStartingRun
                ? "Initializing ADK Swarm..."
                : "Launch Autonomous GTM Engine"}
            </button>
          </div>
        </div>
      </section>

      <MarketAuditCard />
      <AntiICPLockStrip />
      <ICPCardsGrid />
    </div>
  );
}
