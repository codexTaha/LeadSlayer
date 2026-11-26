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
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-xs font-mono uppercase tracking-wider text-zinc-400">
          Slayer Aggression Level
        </label>
        <span className="text-[11px] text-zinc-500">
          Controls Tier 2 &amp; Tier 3 disqualification strictness
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
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
              className={`relative rounded-xl border p-3 text-left transition-all cursor-pointer disabled:opacity-50 ${
                active
                  ? `${meta.accentBorder} ${meta.accentBg} shadow-lg`
                  : "border-zinc-800 bg-zinc-900/50 hover:border-zinc-700"
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Icon
                    className={`h-4 w-4 ${active ? meta.accentText : "text-zinc-400"}`}
                  />
                  <span
                    className={`text-sm font-semibold ${
                      active ? "text-zinc-50" : "text-zinc-300"
                    }`}
                  >
                    {meta.label}
                  </span>
                </div>
                <span
                  className={`rounded-full px-2 py-0.5 text-[10px] font-mono ${
                    active
                      ? `${meta.accentBg} ${meta.accentText}`
                      : "bg-zinc-800 text-zinc-400"
                  }`}
                >
                  {meta.expectedSurvival}
                </span>
              </div>
              <p className="mt-1.5 text-xs text-zinc-400 leading-relaxed">
                {meta.tagline}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
