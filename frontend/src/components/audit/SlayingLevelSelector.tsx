"use client";

import { Flame, Shield, Zap } from "lucide-react";
import { SLAYING_LEVELS } from "@/lib/constants";
import { useLeadSlayerStore } from "@/store/useLeadSlayerStore";
import type { SlayingLevel } from "@/types/contracts";

const ORDER: SlayingLevel[] = ["LENIENT", "NORMAL", "RUTHLESS"];

const ICONS: Record<SlayingLevel, typeof Shield> = {
  LENIENT: Shield,
  NORMAL: Zap,
  RUTHLESS: Flame,
};

export function SlayingLevelSelector({ disabled }: { disabled?: boolean }) {
  const current = useLeadSlayerStore((s) => s.startupInput.slaying_level);
  const updateStartupInput = useLeadSlayerStore((s) => s.updateStartupInput);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <label className="text-xs font-semibold uppercase tracking-wider text-zinc-300">
          Slayer Aggression Level
        </label>
        <span className="text-xs text-zinc-500">
          Controls Tier 2 &amp; Tier 3 disqualification strictness
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
        {ORDER.map((level) => {
          const meta = SLAYING_LEVELS[level];
          const Icon = ICONS[level];
          const active = current === level;

          return (
            <button
              key={level}
              type="button"
              disabled={disabled}
              onClick={() => updateStartupInput({ slaying_level: level })}
              className={`relative rounded-xl border p-4 text-left transition-all cursor-pointer disabled:opacity-50 ${
                active
                  ? `${meta.accentBorder} ${meta.accentBg} ring-1 ring-inset ring-white/15 shadow-[0_10px_28px_rgba(0,0,0,0.35)]`
                  : "border-stone-700/60 bg-[#1D1814] hover:border-stone-600 hover:bg-[#231D18]"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2.5">
                  <div
                    className={`flex h-7 w-7 items-center justify-center rounded-lg border ${
                      active
                        ? `${meta.accentBorder} bg-black/30`
                        : "border-zinc-800 bg-zinc-950/70"
                    }`}
                  >
                    <Icon
                      className={`h-3.5 w-3.5 ${active ? meta.accentText : "text-zinc-500"}`}
                    />
                  </div>
                  <span
                    className={`text-sm font-semibold ${
                      active ? "text-zinc-50" : "text-zinc-300"
                    }`}
                  >
                    {meta.label}
                  </span>
                </div>
                <span
                  className={`rounded-full border px-2.5 py-0.5 text-[11px] font-mono ${
                    active
                      ? `${meta.accentBorder} ${meta.accentBg} ${meta.accentText}`
                      : "border-zinc-800 bg-zinc-900 text-zinc-500"
                  }`}
                >
                  {meta.expectedSurvival}
                </span>
              </div>
              <p className="mt-2.5 text-xs text-zinc-400 leading-relaxed">
                {meta.tagline}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
