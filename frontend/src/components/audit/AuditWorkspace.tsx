"use client";

import { useRef, useState } from "react";
import { motion } from "framer-motion";
import {
  ArrowRight,
  ChevronDown,
  ChevronUp,
  Cpu,
  FileSpreadsheet,
  Globe,
  Layers,
  Loader2,
  Play,
  Search,
  Sparkles,
  Upload,
  Users,
} from "lucide-react";
import { AntiICPLockStrip } from "@/components/audit/AntiICPLockStrip";
import { ICPCardsGrid } from "@/components/audit/ICPCardsGrid";
import { MarketAuditCard } from "@/components/audit/MarketAuditCard";
import { SlayingLevelSelector } from "@/components/audit/SlayingLevelSelector";
import { fetchDemoPreset, parseCsvLeads } from "@/lib/api";
import { useLeadSlayerStore } from "@/store/useLeadSlayerStore";
import type { LeadSourceType } from "@/types/contracts";

interface AuditWorkspaceProps {
  onLaunch: () => void;
}

export function AuditWorkspace({ onLaunch }: AuditWorkspaceProps) {
  const phase = useLeadSlayerStore((s) => s.phase);
  const startupInput = useLeadSlayerStore((s) => s.startupInput);
  const leadOrder = useLeadSlayerStore((s) => s.leadOrder);
  const marketAudit = useLeadSlayerStore((s) => s.marketAudit);
  const icps = useLeadSlayerStore((s) => s.icps);
  const isLoadingPreset = useLeadSlayerStore((s) => s.isLoadingPreset);
  const isStartingRun = useLeadSlayerStore((s) => s.isStartingRun);
  const setIsLoadingPreset = useLeadSlayerStore((s) => s.setIsLoadingPreset);
  const setPresetData = useLeadSlayerStore((s) => s.setPresetData);
  const setCustomLeads = useLeadSlayerStore((s) => s.setCustomLeads);
  const setLeadSources = useLeadSlayerStore((s) => s.setLeadSources);
  const updateStartupInput = useLeadSlayerStore((s) => s.updateStartupInput);
  const setError = useLeadSlayerStore((s) => s.setError);
  const setActiveViewTab = useLeadSlayerStore((s) => s.setActiveViewTab);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [csvLabel, setCsvLabel] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [showLockedConfig, setShowLockedConfig] = useState(false);

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

  const activeSources: LeadSourceType[] =
    startupInput.lead_sources && startupInput.lead_sources.length > 0
      ? startupInput.lead_sources
      : ["CSV_PRESET"];
  const hasAi = activeSources.includes("AI_SEARCH");
  const hasLi = activeSources.includes("LINKEDIN_SEARCH");
  const hasCsv = activeSources.includes("CSV_PRESET");

  const toggleSource = (src: LeadSourceType) => {
    const exists = activeSources.includes(src);
    if (exists && activeSources.length === 1) return;
    const next = exists
      ? activeSources.filter((s) => s !== src)
      : [...activeSources, src];
    setLeadSources(next);
    if (src === "CSV_PRESET" && !exists && leadOrder.length === 0) {
      void handleLoadSample();
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
      {isLocked && !showLockedConfig ? (
        <section className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-zinc-800 bg-zinc-950/90 px-4 py-3">
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <span className="rounded border border-rose-500/40 bg-rose-500/15 px-2 py-0.5 font-mono uppercase text-rose-300">
              Locked Run
            </span>
            <span className="font-semibold text-zinc-100">
              {startupInput.product_name || "Target Startup"}
            </span>
            <span className="text-zinc-500">·</span>
            <span className="font-mono text-emerald-300">
              {leadOrder.length > 0
                ? `${leadOrder.length} Leads Armed`
                : hasAi && hasLi
                  ? "Combined: AI + LinkedIn Hunt"
                  : hasLi
                    ? "LinkedIn Search Active"
                    : "AI Search Active"}
            </span>
            <span className="text-zinc-500">·</span>
            <span className="font-mono text-zinc-400">
              {startupInput.slaying_level} Mode
            </span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowLockedConfig(true)}
              className="inline-flex items-center gap-1 rounded-lg border border-zinc-800 bg-zinc-900 px-2.5 py-1 text-xs text-zinc-300 hover:border-zinc-700 cursor-pointer"
            >
              Show Config
              <ChevronDown className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setActiveViewTab("BLOODBATH")}
              className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1 text-xs font-medium text-zinc-200 hover:bg-zinc-800 cursor-pointer"
            >
              Bloodbath Matrix
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </section>
      ) : (
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

          <div className="flex items-center gap-2">
            {isLocked && (
              <button
                type="button"
                onClick={() => setShowLockedConfig(false)}
                className="inline-flex items-center gap-1 rounded-xl border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs text-zinc-300 hover:bg-zinc-800 cursor-pointer"
              >
                Hide Config
                <ChevronUp className="h-3.5 w-3.5" />
              </button>
            )}
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
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-2 space-y-2">
              <div className="flex items-center justify-between px-1">
                <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-400">
                  Lead Sourcing Mode
                </span>
                <button
                  type="button"
                  disabled={isLocked}
                  onClick={() => setLeadSources(["AI_SEARCH", "LINKEDIN_SEARCH"])}
                  className={`rounded px-1.5 py-0.5 text-[10px] font-mono transition cursor-pointer disabled:opacity-50 ${
                    hasAi && hasLi && !hasCsv
                      ? "bg-indigo-500/30 text-indigo-200 border border-indigo-400/50"
                      : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
                  }`}
                >
                  Combine AI + LinkedIn
                </button>
              </div>

              <div className="grid grid-cols-3 gap-1">
                <button
                  type="button"
                  disabled={isLocked}
                  onClick={() => toggleSource("AI_SEARCH")}
                  className={`inline-flex flex-col items-center justify-center gap-1 rounded-lg px-2 py-2 text-[10px] font-semibold transition cursor-pointer disabled:opacity-50 ${
                    hasAi
                      ? "bg-indigo-500/20 text-indigo-200 border border-indigo-400/50"
                      : "border border-zinc-800 text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  <Search className="h-3.5 w-3.5" />
                  AI Search
                </button>
                <button
                  type="button"
                  disabled={isLocked}
                  onClick={() => toggleSource("LINKEDIN_SEARCH")}
                  className={`inline-flex flex-col items-center justify-center gap-1 rounded-lg px-2 py-2 text-[10px] font-semibold transition cursor-pointer disabled:opacity-50 ${
                    hasLi
                      ? "bg-sky-500/20 text-sky-200 border border-sky-400/50"
                      : "border border-zinc-800 text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  <Users className="h-3.5 w-3.5" />
                  LinkedIn
                </button>
                <button
                  type="button"
                  disabled={isLocked}
                  onClick={() => toggleSource("CSV_PRESET")}
                  className={`inline-flex flex-col items-center justify-center gap-1 rounded-lg px-2 py-2 text-[10px] font-semibold transition cursor-pointer disabled:opacity-50 ${
                    hasCsv
                      ? "bg-emerald-500/15 text-emerald-200 border border-emerald-500/40"
                      : "border border-zinc-800 text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  <FileSpreadsheet className="h-3.5 w-3.5" />
                  CSV / Preset
                </button>
              </div>
            </div>

            {hasCsv ? (
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
                className={`flex-1 flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-4 text-center transition cursor-pointer ${
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
                  <FileSpreadsheet className="h-7 w-7 text-emerald-400 mb-1.5" />
                ) : (
                  <Upload className="h-7 w-7 text-zinc-500 mb-1.5" />
                )}
                <div className="text-xs font-medium text-zinc-100">
                  {leadOrder.length > 0
                    ? `${leadOrder.length} Leads Armed${hasAi || hasLi ? " + Live Hunt" : ""}`
                    : "Drop Lead List CSV"}
                </div>
                <p className="mt-1 text-[11px] text-zinc-400">
                  {csvLabel ||
                    "Supports Apollo / LinkedIn exports or custom .csv"}
                </p>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center rounded-xl border-2 border-indigo-500/40 bg-indigo-950/20 p-4 text-center space-y-2">
                <Globe className="h-7 w-7 text-indigo-300" />
                <div className="text-xs font-semibold text-indigo-100">
                  {hasAi && hasLi
                    ? "Combined: AI Search + LinkedIn Search"
                    : hasLi
                      ? "LinkedIn Search Mode (X-Ray / Harvey)"
                      : "AI Search Mode (Google + Harvey Crawl)"}
                </div>
                <p className="text-[11px] text-zinc-300 leading-relaxed">
                  Discovers real buyers, crawls team pages &amp; ATS hiring boards via{" "}
                  <span className="font-mono text-indigo-300">Harvey</span>, checks DNS MX &amp; resolves emails ($0).
                </p>
                <button
                  type="button"
                  disabled={isLocked}
                  onClick={() => !isLocked && fileInputRef.current?.click()}
                  className="text-[10px] font-mono text-zinc-400 underline hover:text-zinc-200 cursor-pointer"
                >
                  + Also add a custom .csv
                </button>
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
              </div>
            )}

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

        <div className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <label className="text-xs font-semibold uppercase tracking-wider text-zinc-300">
                Target Qualified Leads Goal
              </label>
              <p className="text-[11px] text-zinc-500">
                Autonomous Hunter + Slayer will hunt until reaching this number of qualified survivors (peaked at 50 for live demo).
              </p>
            </div>
            <span className="font-mono text-sm font-bold text-emerald-400 bg-emerald-950/50 border border-emerald-800/60 px-3 py-1 rounded-lg">
              {startupInput.target_qualified_leads ?? 10} Qualified Survivors
            </span>
          </div>
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={5}
              max={50}
              step={5}
              disabled={isLocked}
              value={startupInput.target_qualified_leads ?? 10}
              onChange={(e) =>
                updateStartupInput({ target_qualified_leads: Number(e.target.value) })
              }
              className="w-full accent-emerald-500 cursor-pointer disabled:opacity-50"
            />
          </div>
          <div className="flex justify-between text-[10px] font-mono text-zinc-500">
            <span>5 (Quick Test)</span>
            <span>15 (Balanced)</span>
            <span>30 (Deep Market)</span>
            <span className="text-emerald-400 font-semibold">50 (Demo Max)</span>
          </div>
        </div>

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
      )}

      {phase === "AUDITING" && !marketAudit && (
        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-indigo-500/35 bg-zinc-950/90 p-5 space-y-4"
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 text-sm font-semibold text-indigo-200">
              <Globe className="h-4 w-4 text-indigo-400 animate-spin" />
              Step 1 · Market Auditor Analyzing Product Context &amp; Assumptions...
            </div>
            <span className="text-[11px] font-mono text-indigo-400">
              GEMINI BRAIN
            </span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {[
              "Scraping product narrative & technical wedge",
              "Challenging founder assumptions vs. market reality",
              "Computing readiness rubric & Anti-ICP red flags",
            ].map((label, idx) => (
              <div
                key={label}
                className="rounded-lg border border-zinc-800/80 bg-zinc-900/50 p-3 space-y-2"
              >
                <div className="text-xs text-zinc-300">{label}</div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
                  <motion.div
                    className="h-full rounded-full bg-indigo-400"
                    initial={{ width: "12%" }}
                    animate={{ width: ["20%", "88%", "55%"] }}
                    transition={{
                      duration: 1.8,
                      repeat: Infinity,
                      delay: idx * 0.25,
                      ease: "easeInOut",
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </motion.section>
      )}

      {phase === "ICP_GENERATION" && (
        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-emerald-500/35 bg-zinc-950/90 p-5 space-y-4"
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 text-sm font-semibold text-emerald-200">
              <Cpu className="h-4 w-4 text-emerald-400 animate-pulse" />
              {icps.length === 0
                ? "Step 2 · Synthesizing 3 Non-Overlapping Ideal Customer Profiles..."
                : "Step 2 · Indexing ICPs, Anti-ICPs & 50 Leads into 768d Vector Memory..."}
            </div>
            <span className="inline-flex items-center gap-1.5 rounded border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-[11px] font-mono text-emerald-300">
              <Layers className="h-3 w-3" />
              gemini-embedding-2 (768d)
            </span>
          </div>
          <div className="grid grid-cols-6 sm:grid-cols-12 gap-1.5">
            {Array.from({ length: 12 }).map((_, idx) => (
              <div
                key={idx}
                className="h-8 rounded bg-zinc-900 border border-zinc-800/80 overflow-hidden flex items-end p-0.5"
              >
                <motion.div
                  className="w-full rounded-sm bg-emerald-400/70"
                  animate={{ height: ["20%", "95%", "35%"] }}
                  transition={{
                    duration: 1.1,
                    repeat: Infinity,
                    delay: idx * 0.08,
                    ease: "easeInOut",
                  }}
                />
              </div>
            ))}
          </div>
        </motion.section>
      )}

      <MarketAuditCard />
      <AntiICPLockStrip />
      <ICPCardsGrid />
    </div>
  );
}
