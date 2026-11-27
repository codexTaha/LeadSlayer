"use client";

import { useRef, useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  ArrowRight,
  ChevronDown,
  ChevronUp,
  Cpu,
  Download,
  FileSpreadsheet,
  Globe,
  Layers,
  Loader2,
  Play,
  Search,
  SlidersHorizontal,
  Upload,
  Users,
} from "lucide-react";
import { AntiICPLockStrip } from "@/components/audit/AntiICPLockStrip";
import { ICPCardsGrid } from "@/components/audit/ICPCardsGrid";
import { MarketAuditCard } from "@/components/audit/MarketAuditCard";
import { SlayingLevelSelector } from "@/components/audit/SlayingLevelSelector";
import { fetchSavedExports, parseCsvLeads } from "@/lib/api";
import { useLeadSlayerStore } from "@/store/useLeadSlayerStore";
import type { LeadSourceType, SavedExportSummary } from "@/types/contracts";

interface AuditWorkspaceProps {
  onLaunch: () => void;
}

export function AuditWorkspace({ onLaunch }: AuditWorkspaceProps) {
  const phase = useLeadSlayerStore((s) => s.phase);
  const startupInput = useLeadSlayerStore((s) => s.startupInput);
  const leadOrder = useLeadSlayerStore((s) => s.leadOrder);
  const marketAudit = useLeadSlayerStore((s) => s.marketAudit);
  const icps = useLeadSlayerStore((s) => s.icps);
  const isStartingRun = useLeadSlayerStore((s) => s.isStartingRun);
  const setCustomLeads = useLeadSlayerStore((s) => s.setCustomLeads);
  const setLeadSources = useLeadSlayerStore((s) => s.setLeadSources);
  const updateStartupInput = useLeadSlayerStore((s) => s.updateStartupInput);
  const setError = useLeadSlayerStore((s) => s.setError);
  const setActiveViewTab = useLeadSlayerStore((s) => s.setActiveViewTab);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [csvLabel, setCsvLabel] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [showLockedConfig, setShowLockedConfig] = useState(false);
  const [savedExports, setSavedExports] = useState<SavedExportSummary[]>([]);

  useEffect(() => {
    void fetchSavedExports()
      .then((items) => setSavedExports(items))
      .catch(() => {});
  }, [phase]);

  const isLocked = phase !== "IDLE" && phase !== "ERROR";

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
      : ["AI_SEARCH", "LINKEDIN_SEARCH"];
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
            <span className="text-zinc-600">·</span>
            <span className="font-mono text-emerald-300">
              {leadOrder.length > 0
                ? `${leadOrder.length} Leads Armed`
                : hasAi && hasLi
                  ? "Combined: AI + LinkedIn Hunt"
                  : hasLi
                    ? "LinkedIn Search Active"
                    : "AI Search Active"}
            </span>
            <span className="text-zinc-600">·</span>
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
        <div className="space-y-8">
          {/* Top Title & Quick Presets Bar */}
          <div className="flex flex-wrap items-end justify-between gap-4 px-1">
            <div>
              <span className="text-[11px] font-mono uppercase tracking-widest text-rose-400">
                Act 1 · Campaign Setup
              </span>
              <h1 className="text-2xl font-bold tracking-tight text-stone-50 mt-0.5">
                Define Your Product. Let LeadSlayer Slaughter the Noise.
              </h1>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {isLocked && (
                <button
                  type="button"
                  onClick={() => setShowLockedConfig(false)}
                  className="inline-flex items-center gap-1 rounded-xl border border-stone-600 bg-[#26221E] px-3 py-2 text-xs text-stone-200 hover:bg-[#302A24] cursor-pointer"
                >
                  Hide Config
                  <ChevronUp className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Segment 1 & 2 Grid: Product Context (Left) + Lead Pipeline Input (Right) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-7 items-stretch">
            {/* Segment 1: Product & Hypothesis (Deep Indigo-Slate Surface) */}
            <section className="lg:col-span-7 rounded-2xl border border-indigo-400/30 bg-[#1F2436] p-6 sm:p-7 shadow-[0_18px_45px_rgba(0,0,0,0.42)] flex flex-col justify-between space-y-5">
              <div className="flex items-center justify-between border-b border-indigo-300/15 pb-3.5">
                <div className="flex items-center gap-2.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-indigo-400 shadow-[0_0_8px_#818cf8]" />
                  <h2 className="text-xs font-mono uppercase tracking-wider text-indigo-100 font-semibold">
                    1 · Product &amp; Founder Hypothesis
                  </h2>
                </div>
                <span className="text-[11px] font-mono text-indigo-300/70">
                  Audited by gemini-4-hydrogen
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-indigo-100/90 mb-1.5">
                    Startup / Product Name
                  </label>
                  <input
                    type="text"
                    disabled={isLocked}
                    value={startupInput.product_name}
                    onChange={(e) =>
                      updateStartupInput({ product_name: e.target.value })
                    }
                    placeholder="e.g. Acme Cloud"
                    className="w-full rounded-xl border border-indigo-300/20 bg-[#151826] px-3.5 py-2.5 text-sm text-stone-100 placeholder:text-stone-500 focus:border-indigo-400 focus:outline-none disabled:opacity-60"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-indigo-100/90 mb-1.5">
                    Website URL{" "}
                    <span className="text-indigo-200/55 font-normal">(Live Crawl)</span>
                  </label>
                  <input
                    type="text"
                    disabled={isLocked}
                    value={startupInput.product_url ?? ""}
                    onChange={(e) =>
                      updateStartupInput({ product_url: e.target.value })
                    }
                    placeholder="https://example.com"
                    className="w-full rounded-xl border border-indigo-300/20 bg-[#151826] px-3.5 py-2.5 text-sm text-stone-100 placeholder:text-stone-500 focus:border-indigo-400 focus:outline-none disabled:opacity-60"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-indigo-100/90 mb-1.5">
                  Product Description &amp; Technical Edge
                </label>
                <textarea
                  rows={5}
                  disabled={isLocked}
                  value={startupInput.description}
                  onChange={(e) =>
                    updateStartupInput({ description: e.target.value })
                  }
                  placeholder="Describe what your product builds, target buyers, and core ROI..."
                  className="w-full rounded-xl border border-indigo-300/20 bg-[#151826] px-3.5 py-2.5 text-sm leading-relaxed text-stone-100 placeholder:text-stone-500 focus:border-indigo-400 focus:outline-none disabled:opacity-60 resize-y"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-indigo-100/90 mb-1.5">
                  Founder&apos;s Market Assumptions{" "}
                  <span className="text-indigo-200/55 font-normal">(What Auditor Will Challenge)</span>
                </label>
                <textarea
                  rows={2}
                  disabled={isLocked}
                  value={startupInput.founder_assumptions}
                  onChange={(e) =>
                    updateStartupInput({ founder_assumptions: e.target.value })
                  }
                  placeholder="e.g. Any company in this market needs our solution..."
                  className="w-full rounded-xl border border-indigo-300/20 bg-[#151826] px-3.5 py-2.5 text-sm leading-relaxed text-stone-100 placeholder:text-stone-500 focus:border-indigo-400 focus:outline-none disabled:opacity-60 resize-none"
                />
              </div>
            </section>

            {/* Segment 2: Lead Sourcing & Swarm (Deep Emerald-Teal Surface) */}
            <section className="lg:col-span-5 rounded-2xl border border-emerald-400/30 bg-[#192825] p-6 sm:p-7 shadow-[0_18px_45px_rgba(0,0,0,0.42)] flex flex-col justify-between gap-5">
              <div className="flex items-center justify-between border-b border-emerald-300/15 pb-3.5">
                <div className="flex items-center gap-2.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" />
                  <h2 className="text-xs font-mono uppercase tracking-wider text-emerald-100 font-semibold">
                    2 · Lead Sourcing Mode
                  </h2>
                </div>
                <button
                  type="button"
                  disabled={isLocked}
                  onClick={() => setLeadSources(["AI_SEARCH", "LINKEDIN_SEARCH"])}
                  className={`rounded-lg px-2.5 py-1 text-[11px] font-mono transition cursor-pointer disabled:opacity-50 ${
                    hasAi && hasLi && !hasCsv
                      ? "bg-emerald-500/25 text-emerald-100 border border-emerald-400/50"
                      : "border border-emerald-300/20 bg-[#121E1C] text-emerald-200/75 hover:text-emerald-100"
                  }`}
                >
                  Combine AI + LinkedIn
                </button>
              </div>

              <div className="grid grid-cols-3 gap-2.5">
                <button
                  type="button"
                  disabled={isLocked}
                  onClick={() => toggleSource("AI_SEARCH")}
                  className={`inline-flex flex-col items-center justify-center gap-1.5 rounded-xl px-3 py-3 text-xs font-semibold transition cursor-pointer disabled:opacity-50 ${
                    hasAi
                      ? "bg-indigo-500/25 text-indigo-100 border border-indigo-400/60 shadow-sm"
                      : "border border-emerald-300/15 bg-[#121E1C] text-stone-300 hover:border-emerald-300/35"
                  }`}
                >
                  <Search className="h-4 w-4" />
                  AI Search
                </button>
                <button
                  type="button"
                  disabled={isLocked}
                  onClick={() => toggleSource("LINKEDIN_SEARCH")}
                  className={`inline-flex flex-col items-center justify-center gap-1.5 rounded-xl px-3 py-3 text-xs font-semibold transition cursor-pointer disabled:opacity-50 ${
                    hasLi
                      ? "bg-sky-500/25 text-sky-100 border border-sky-400/60 shadow-sm"
                      : "border border-emerald-300/15 bg-[#121E1C] text-stone-300 hover:border-emerald-300/35"
                  }`}
                >
                  <Users className="h-4 w-4" />
                  LinkedIn
                </button>
                <button
                  type="button"
                  disabled={isLocked}
                  onClick={() => toggleSource("CSV_PRESET")}
                  className={`inline-flex flex-col items-center justify-center gap-1.5 rounded-xl px-3 py-3 text-xs font-semibold transition cursor-pointer disabled:opacity-50 ${
                    hasCsv
                      ? "bg-emerald-500/25 text-emerald-100 border border-emerald-400/60 shadow-sm"
                      : "border border-emerald-300/15 bg-[#121E1C] text-stone-300 hover:border-emerald-300/35"
                  }`}
                >
                  <FileSpreadsheet className="h-4 w-4" />
                  CSV / Preset
                </button>
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
                  className={`flex-1 min-h-[176px] flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-5 text-center transition cursor-pointer ${
                    isDragging
                      ? "border-rose-400 bg-rose-500/15"
                      : "border-emerald-300/25 bg-[#121E1C] hover:border-emerald-300/50 hover:bg-[#152421]"
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
                    <Upload className="h-8 w-8 text-emerald-200/60 mb-2" />
                  )}
                  <div className="text-sm font-semibold text-stone-100">
                    {leadOrder.length > 0
                      ? `${leadOrder.length} Leads Armed${hasAi || hasLi ? " + Live Hunt" : ""}`
                      : "Drop Lead List .CSV Here"}
                  </div>
                  <p className="mt-1 text-xs text-emerald-100/70">
                    {csvLabel || "Supports Apollo / LinkedIn exports or custom .csv"}
                  </p>
                </div>
              ) : (
                <div className="flex-1 min-h-[176px] flex flex-col items-center justify-center rounded-xl border border-emerald-300/25 bg-[#121E1C] p-5 text-center space-y-2.5">
                  <Globe className="h-8 w-8 text-emerald-300" />
                  <div className="text-sm font-semibold text-emerald-50">
                    {hasAi && hasLi
                      ? "Combined: AI Search + LinkedIn Search"
                      : hasLi
                        ? "LinkedIn Search Mode (X-Ray / Live Crawl)"
                        : "AI Search Mode (Google + Live Crawl)"}
                  </div>
                  <p className="text-xs text-emerald-100/75 leading-relaxed max-w-xs">
                    Discovers live buyers, crawls team pages &amp; ATS hiring boards via{" "}
                    <span className="font-mono text-emerald-300">LeadSlayer Crawler</span>, and verifies DNS MX records.
                  </p>
                  <button
                    type="button"
                    disabled={isLocked}
                    onClick={() => !isLocked && fileInputRef.current?.click()}
                    className="text-xs font-mono text-emerald-200/70 underline hover:text-emerald-100 cursor-pointer"
                  >
                    + Also attach a custom .csv
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

              <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-emerald-300/15 bg-[#121E1C] px-3.5 py-2.5 text-[11px] font-mono text-stone-300">
                <span className="text-emerald-200/60">Models:</span>
                <span className="text-indigo-300">4-hydrogen</span>
                <span className="text-stone-600">·</span>
                <span className="text-rose-300">3.5-flash-lite</span>
                <span className="text-stone-600">·</span>
                <span className="text-emerald-300">embedding-2</span>
              </div>
            </section>
          </div>

          {/* Segment 3: Qualification Rules & Survivor Cap (Warm Bronze-Amber Surface) */}
          <section className="rounded-2xl border border-amber-400/30 bg-[#28211B] p-6 sm:p-7 shadow-[0_18px_45px_rgba(0,0,0,0.42)] space-y-6">
            <div className="flex items-center justify-between border-b border-amber-300/15 pb-3.5">
              <div className="flex items-center gap-2.5">
                <SlidersHorizontal className="h-4 w-4 text-amber-400" />
                <h2 className="text-xs font-mono uppercase tracking-wider text-amber-100 font-semibold">
                  3 · Qualification Guardrails &amp; Target Goal
                </h2>
              </div>
              <span className="text-[11px] font-mono text-amber-200/65">
                Zero-Survivor Auto-Recovery Active
              </span>
            </div>

            <SlayingLevelSelector disabled={isLocked} />

            <div className="border-t border-amber-300/15 pt-6 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wider text-amber-100">
                    Target Qualified Leads Goal
                  </label>
                  <p className="text-xs text-stone-400 mt-0.5">
                    Autonomous Hunter + Slayer hunts until reaching this survivor cap (max 50).
                  </p>
                </div>
                <span className="font-mono text-xs font-bold text-amber-200 bg-[#1B1612] border border-amber-400/40 px-3 py-1.5 rounded-lg">
                  {startupInput.target_qualified_leads ?? 10} Qualified Survivors
                </span>
              </div>

              <input
                type="range"
                min={5}
                max={50}
                step={5}
                disabled={isLocked}
                value={startupInput.target_qualified_leads ?? 10}
                onChange={(e) =>
                  updateStartupInput({
                    target_qualified_leads: Number(e.target.value),
                  })
                }
                className="w-full accent-amber-400 cursor-pointer disabled:opacity-50"
              />

              <div className="flex justify-between text-[11px] font-mono text-stone-400">
                <span>5 (Quick Test)</span>
                <span>15 (Balanced)</span>
                <span>30 (Deep Market)</span>
                <span className="text-amber-300 font-semibold">50 (Demo Max)</span>
              </div>
            </div>
          </section>

          {/* Dedicated Launch Action Footer (Warm Crimson-Charcoal Surface) */}
          <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-rose-400/35 bg-[#2A1D22] px-6 py-4 shadow-[0_16px_40px_rgba(0,0,0,0.45)]">
            <div className="flex flex-wrap items-center gap-2.5 text-xs font-mono text-rose-100/90">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-[0_0_8px_#34d399]" />
              <span>
                {phase === "IDLE"
                  ? `Ready · ${startupInput.product_name || "Custom Product"} · ${
                      leadOrder.length > 0 ? `${leadOrder.length} Leads` : "Live Discovery"
                    } · ${startupInput.slaying_level}`
                  : `Pipeline active: ${phase}`}
              </span>
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
                className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-rose-600 to-rose-500 px-6 py-3 text-sm font-semibold text-white shadow-[0_0_25px_rgba(244,63,94,0.35)] transition hover:from-rose-500 hover:to-rose-400 cursor-pointer disabled:opacity-45 disabled:shadow-none disabled:cursor-not-allowed"
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
        </div>
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
                : "Step 2 · Indexing ICPs, Anti-ICPs & Leads into 768d Vector Memory..."}
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

      {savedExports.length > 0 && (
        <section className="rounded-xl border border-stone-700/60 bg-[#201D1A] p-4 space-y-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-emerald-300">
              <FileSpreadsheet className="h-4 w-4 text-emerald-400" />
              Saved Verified Lead CSV Exports
            </div>
            <span className="text-[11px] font-mono text-zinc-500">
              Web &amp; MCP Runs
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
            {savedExports.slice(0, 6).map((item) => (
              <div
                key={item.run_id}
                className="flex items-center justify-between gap-3 rounded-lg border border-zinc-800 bg-zinc-950/70 px-3 py-2.5"
              >
                <div className="min-w-0">
                  <div className="truncate text-xs font-semibold text-zinc-100">
                    {item.product_name}
                  </div>
                  <div className="text-[11px] font-mono text-zinc-400">
                    {item.verified_count} verified · {item.run_id}
                  </div>
                </div>
                <a
                  href={item.csv_url}
                  download
                  className="shrink-0 inline-flex items-center gap-1 rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1.5 text-[11px] font-semibold text-emerald-200 hover:bg-emerald-500/20 transition"
                >
                  <Download className="h-3 w-3 text-emerald-400" />
                  CSV
                </a>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
