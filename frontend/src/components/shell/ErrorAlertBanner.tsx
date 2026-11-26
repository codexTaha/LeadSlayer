"use client";

import { AlertTriangle, RotateCcw, X } from "lucide-react";
import { useLeadSlayerStore } from "@/store/useLeadSlayerStore";

interface ErrorAlertBannerProps {
  onRetry?: () => void;
}

export function ErrorAlertBanner({ onRetry }: ErrorAlertBannerProps) {
  const errorMessage = useLeadSlayerStore((s) => s.errorMessage);
  const setError = useLeadSlayerStore((s) => s.setError);

  if (!errorMessage) return null;

  return (
    <div
      role="alert"
      className="mx-auto w-full max-w-7xl px-4 pt-3 sm:px-6"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rose-500/40 bg-rose-950/40 px-4 py-3 text-sm text-rose-100 shadow-lg backdrop-blur">
        <div className="flex items-center gap-3">
          <AlertTriangle className="h-5 w-5 shrink-0 text-rose-400" />
          <span>{errorMessage}</span>
        </div>
        <div className="flex items-center gap-2">
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="inline-flex items-center gap-1.5 rounded-lg border border-rose-400/50 bg-rose-500/20 px-3 py-1 text-xs font-medium text-rose-100 hover:bg-rose-500/30 cursor-pointer"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Retry Run
            </button>
          )}
          <button
            type="button"
            aria-label="Dismiss error"
            onClick={() => setError(null)}
            className="rounded-lg p-1 text-rose-300 hover:bg-rose-500/20 cursor-pointer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
