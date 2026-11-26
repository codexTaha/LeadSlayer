"use client";

import type { ReactNode } from "react";
import { Crosshair, RotateCcw } from "lucide-react";
import { PhaseStepper } from "@/components/shell/PhaseStepper";
import { ErrorAlertBanner } from "@/components/shell/ErrorAlertBanner";
import { SLAYING_LEVELS } from "@/lib/constants";
import { useLeadSlayerStore } from "@/store/useLeadSlayerStore";

interface CommandCenterShellProps {
  children: ReactNode;
  onRetryRun?: () => void;
}

export function CommandCenterShell({
  children,
  onRetryRun,
}: CommandCenterShellProps) {
  const phase = useLeadSlayerStore((s) => s.phase);
  const executionMode = useLeadSlayerStore((s) => s.executionMode);
  const slayingLevel = useLeadSlayerStore((s) => s.startupInput.slaying_level);
  const telemetry = useLeadSlayerStore((s) => s.telemetry);
  const resetDemo = useLeadSlayerStore((s) => s.resetDemo);

  const levelMeta = SLAYING_LEVELS[slayingLevel];

  return (
    <div className="min-h-screen flex flex-col bg-[#07090D] text-zinc-100">
      <header className="sticky top-0 z-30 border-b border-zinc-800/80 bg-[#07090D]/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl flex-col gap-2.5 px-4 py-3 sm:px-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-rose-500/40 bg-rose-500/15 shadow-[0_0_20px_rgba(244,63,94,0.2)]">
                <Crosshair className="h-5 w-5 text-rose-400" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-base font-bold tracking-tight text-zinc-50">
                    LeadSlayer AI
                  </span>
                  <span className="rounded border border-zinc-700/80 bg-zinc-900 px-1.5 py-0.5 text-[10px] font-mono uppercase tracking-wider text-zinc-400">
                    ADK 2.0
                  </span>
                  <span
                    className={`rounded border px-1.5 py-0.5 text-[10px] font-mono uppercase tracking-wider ${levelMeta.accentBorder} ${levelMeta.accentBg} ${levelMeta.accentText}`}
                  >
                    {levelMeta.label} Mode
                  </span>
                </div>
                <p className="text-xs text-zinc-400">
                  Autonomous GTM Command Center — Slaughter Spam, Sniper Survivors
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2.5">
              {telemetry && (
                <div className="hidden md:flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/70 px-3 py-1.5 text-xs font-mono">
                  <span className="text-rose-400">
                    {telemetry.killed_count} KILLED
                  </span>
                  <span className="text-zinc-600">|</span>
                  <span className="text-emerald-400">
                    {telemetry.survived_count} SURVIVED
                  </span>
                  <span className="text-zinc-600">|</span>
                  <span className="text-zinc-300">
                    {telemetry.kill_rate_pct.toFixed(0)}% KILL RATE
                  </span>
                </div>
              )}

              <div
                title={
                  executionMode === "LIVE"
                    ? "Running Live Google Gemini API"
                    : "Replaying Authentic Cached Gemini Session"
                }
                className="inline-flex items-center gap-1.5 rounded-full border border-zinc-800 bg-zinc-900/80 px-2.5 py-1 text-[11px] font-mono text-zinc-300"
              >
                <span
                  className={`h-2 w-2 rounded-full ${
                    executionMode === "LIVE"
                      ? "bg-emerald-400 shadow-[0_0_8px_#34d399]"
                      : "bg-amber-400 shadow-[0_0_8px_#fbbf24]"
                  }`}
                />
                {executionMode === "LIVE" ? "LIVE GEMINI" : "CACHED REPLAY"}
              </div>

              {phase !== "IDLE" && (
                <button
                  type="button"
                  onClick={resetDemo}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs font-medium text-zinc-200 transition hover:border-zinc-500 hover:bg-zinc-800 cursor-pointer"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  Reset Demo
                </button>
              )}
            </div>
          </div>

          <PhaseStepper />
        </div>
      </header>

      <ErrorAlertBanner onRetry={onRetryRun} />

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6">
        {children}
      </main>
    </div>
  );
}
