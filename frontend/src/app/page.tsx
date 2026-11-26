"use client";

import { useEffect, useState } from "react";
import { Activity, CheckCircle2, Crosshair, ShieldAlert } from "lucide-react";
import type { HealthResponse, PresetResponse } from "@/types/contracts";

export default function Stage1HealthPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [preset, setPreset] = useState<PresetResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function checkBackend() {
      try {
        const [healthRes, presetRes] = await Promise.all([
          fetch("/api/health"),
          fetch("/api/demo/preset"),
        ]);
        if (!healthRes.ok || !presetRes.ok) {
          throw new Error(
            `Backend check failed (${healthRes.status}/${presetRes.status})`
          );
        }
        const [healthJson, presetJson] = (await Promise.all([
          healthRes.json(),
          presetRes.json(),
        ])) as [HealthResponse, PresetResponse];
        if (active) {
          setHealth(healthJson);
          setPreset(presetJson);
        }
      } catch (err) {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to reach FastAPI backend on port 8000."
          );
        }
      }
    }
    checkBackend();
    return () => {
      active = false;
    };
  }, []);

  return (
    <main className="min-h-screen bg-[#07090D] text-zinc-100 p-8 flex flex-col items-center justify-center">
      <div className="w-full max-w-2xl rounded-xl border border-zinc-800 bg-zinc-950/90 p-6 shadow-2xl space-y-5">
        <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
          <div className="flex items-center gap-3">
            <Crosshair className="w-6 h-6 text-rose-500" />
            <div>
              <h1 className="text-lg font-semibold tracking-tight">
                LeadSlayer AI — Stage 1 Contract & Proxy Check
              </h1>
              <p className="text-xs text-zinc-400">
                Verifying Next.js ↔ FastAPI typed contracts & 50-lead dataset
              </p>
            </div>
          </div>
          <span className="inline-flex items-center gap-1.5 rounded-full border border-zinc-700 px-2.5 py-1 text-xs font-mono text-zinc-300">
            <Activity className="w-3.5 h-3.5 text-emerald-400" />
            STAGE 1
          </span>
        </div>

        {error && (
          <div className="flex items-center gap-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-200">
            <ShieldAlert className="w-5 h-5 shrink-0 text-amber-400" />
            <span>
              Backend offline right now ({error}). Start FastAPI with{" "}
              <code className="font-mono text-amber-100">
                uvicorn app.main:app --port 8000
              </code>{" "}
              and refresh.
            </span>
          </div>
        )}

        {health && (
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 space-y-2">
            <div className="flex items-center gap-2 text-emerald-300 text-sm font-medium">
              <CheckCircle2 className="w-4 h-4" />
              Backend Connected ({health.status.toUpperCase()})
            </div>
            <div className="grid grid-cols-3 gap-2 text-xs font-mono text-zinc-300">
              <div className="rounded bg-zinc-900/80 p-2 border border-zinc-800">
                Brain: {health.models.brain}
              </div>
              <div className="rounded bg-zinc-900/80 p-2 border border-zinc-800">
                Workhorse: {health.models.workhorse}
              </div>
              <div className="rounded bg-zinc-900/80 p-2 border border-zinc-800">
                Memory: {health.models.embedding}
              </div>
            </div>
          </div>
        )}

        {preset && (
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4 space-y-1 text-sm">
            <div className="font-medium text-zinc-100">
              Preset Loaded: {preset.startup.product_name} (
              {preset.leads.length} leads)
            </div>
            <p className="text-xs text-zinc-400">
              Default Mode: {preset.startup.slaying_level} | First Lead:{" "}
              {preset.leads[0]?.full_name} ({preset.leads[0]?.company})
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
