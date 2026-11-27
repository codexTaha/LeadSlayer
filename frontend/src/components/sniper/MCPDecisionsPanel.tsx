"use client";

import { useEffect, useState } from "react";
import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Cpu,
  PlugZap,
  ShieldAlert,
  Terminal,
  Wrench,
} from "lucide-react";
import { fetchMcpStatus } from "@/lib/api";
import { useLeadSlayerStore } from "@/store/useLeadSlayerStore";
import type { MCPStatusResponse } from "@/types/contracts";

export function MCPDecisionsPanel() {
  const mcpToolCalls = useLeadSlayerStore((s) => s.mcpToolCalls);
  const phase = useLeadSlayerStore((s) => s.phase);
  const [mcpStatus, setMcpStatus] = useState<MCPStatusResponse | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    void fetchMcpStatus()
      .then((res) => setMcpStatus(res))
      .catch(() => {});
  }, []);

  if (mcpToolCalls.length === 0 && !mcpStatus) {
    return null;
  }

  return (
    <section className="rounded-xl border border-violet-400/25 bg-[#1D1B29]/90 overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full flex-wrap items-center justify-between gap-3 px-4 py-3 text-left hover:bg-white/[0.03] transition cursor-pointer"
      >
        <div className="flex items-center gap-2.5">
          <PlugZap className="h-4 w-4 text-indigo-300 shrink-0" />
          <span className="text-xs font-semibold text-zinc-200">
            MCP Agent Activity
          </span>
          <span className="rounded border border-indigo-500/35 bg-indigo-500/10 px-2 py-0.5 text-[10px] font-mono text-indigo-300">
            {mcpStatus?.server_name || "leadslayer-ops-mcp"}
          </span>
          <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/35 bg-emerald-500/10 px-2 py-0.5 text-[11px] font-mono text-emerald-300">
            <Cpu className="h-3 w-3" />
            {mcpToolCalls.length} Calls Executed
          </span>
        </div>

        <span className="inline-flex items-center gap-1 text-xs font-mono text-zinc-400">
          {expanded ? "Hide Details" : "Show Details"}
          {expanded ? (
            <ChevronUp className="h-4 w-4" />
          ) : (
            <ChevronDown className="h-4 w-4" />
          )}
        </span>
      </button>

      {expanded && (
        <div className="border-t border-zinc-800/80 p-4 space-y-3">
          {mcpToolCalls.length === 0 ? (
            <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/40 px-4 py-3 text-xs font-mono text-zinc-400 flex items-center gap-2">
              <Terminal className="h-4 w-4 text-zinc-500" />
              {phase === "SNIPING"
                ? "OutreachMCPAgent is evaluating survivors and selecting MCP tools..."
                : "MCP tool execution trace will appear here once survivors are actioned."}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {mcpToolCalls.map((call) => {
                const isBlocked = call.status === "BLOCKED" || call.status === "FAILED";
                return (
                  <div
                    key={call.id}
                    className={`rounded-xl border p-3.5 space-y-2 ${
                      isBlocked
                        ? "border-amber-500/35 bg-amber-950/15"
                        : "border-zinc-800 bg-zinc-900/50"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-1.5 text-xs font-mono text-indigo-300">
                        <Wrench className="h-3.5 w-3.5 shrink-0" />
                        <span className="font-semibold">{call.tool_name}</span>
                      </div>
                      <span
                        className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-mono uppercase ${
                          isBlocked
                            ? "border border-amber-500/40 bg-amber-500/15 text-amber-300"
                            : "border border-emerald-500/40 bg-emerald-500/15 text-emerald-300"
                        }`}
                      >
                        {isBlocked ? (
                          <ShieldAlert className="h-3 w-3" />
                        ) : (
                          <CheckCircle2 className="h-3 w-3" />
                        )}
                        {call.status}
                      </span>
                    </div>

                    <p className="text-xs text-zinc-200 leading-relaxed">
                      <span className="font-mono text-[10px] uppercase text-zinc-400 mr-1.5">
                        Decision:
                      </span>
                      {call.decision_reason}
                    </p>

                    {call.arguments_summary && (
                      <div className="rounded bg-zinc-950/80 px-2.5 py-1 text-[11px] font-mono text-zinc-400 truncate">
                        args: {call.arguments_summary}
                      </div>
                    )}

                    {call.result_summary && (
                      <div className="rounded bg-zinc-950/80 px-2.5 py-1 text-[11px] font-mono text-emerald-300/90 truncate">
                        out: {call.result_summary}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
