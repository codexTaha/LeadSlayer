"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Cpu, Link2, Sparkles } from "lucide-react";
import type { EmailDraft, SlayerVerdict } from "@/types/contracts";

interface EvidenceHighlightedBodyProps {
  draft: EmailDraft;
  verdict?: SlayerVerdict;
}

export function EvidenceHighlightedBody({
  draft,
  verdict,
}: EvidenceHighlightedBodyProps) {
  const [showProof, setShowProof] = useState(false);

  const phrase = draft.email_evidence_phrase.trim();
  const body = draft.body;
  const lowerBody = body.toLowerCase();
  const matchIdx = phrase ? lowerBody.indexOf(phrase.toLowerCase()) : -1;

  const icpMatchPct = verdict
    ? Math.round(verdict.icp_similarity_score * 100)
    : draft.personalization_score;

  const renderBody = () => {
    if (matchIdx === -1) {
      return <p className="whitespace-pre-line">{body}</p>;
    }
    const before = body.slice(0, matchIdx);
    const exactMatch = body.slice(matchIdx, matchIdx + phrase.length);
    const after = body.slice(matchIdx + phrase.length);

    return (
      <p className="whitespace-pre-line">
        {before}
        <span
          className="relative inline-block"
          onMouseEnter={() => setShowProof(true)}
          onMouseLeave={() => setShowProof(false)}
        >
          <mark
            onClick={() => setShowProof((v) => !v)}
            className="cursor-pointer rounded border-b border-emerald-400 bg-emerald-500/20 px-1 py-0.5 text-emerald-200 transition hover:bg-emerald-500/30"
          >
            {exactMatch}
          </mark>

          <AnimatePresence>
            {showProof && (
              <motion.div
                initial={{ opacity: 0, y: 6, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 4, scale: 0.97 }}
                transition={{ duration: 0.15 }}
                className="absolute left-0 top-full z-30 mt-2 w-72 sm:w-80 rounded-xl border border-emerald-500/40 bg-[#0A0F14] p-3.5 text-xs shadow-2xl"
              >
                <div className="flex items-center justify-between border-b border-zinc-800 pb-2 mb-2">
                  <span className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase text-emerald-400">
                    <Link2 className="h-3 w-3" />
                    Zero-Hallucination Evidence Trace
                  </span>
                  <span className="rounded bg-emerald-500/15 px-1.5 py-0.5 font-mono text-[10px] text-emerald-300">
                    {icpMatchPct}% ICP Match
                  </span>
                </div>

                <div className="space-y-2">
                  <div>
                    <div className="flex items-center gap-1 text-[10px] font-mono uppercase text-zinc-500">
                      <Sparkles className="h-3 w-3 text-amber-400" />
                      Lead Buying Signal
                    </div>
                    <p className="text-zinc-200 mt-0.5">
                      {draft.cited_survival_signal}
                    </p>
                  </div>

                  <div>
                    <div className="flex items-center gap-1 text-[10px] font-mono uppercase text-zinc-500">
                      <Cpu className="h-3 w-3 text-indigo-400" />
                      Stage 2 Retrieved Product Match
                    </div>
                    <p className="text-indigo-200/90 mt-0.5">
                      {draft.matched_product_chunk}
                    </p>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </span>
        {after}
      </p>
    );
  };

  return (
    <div className="text-xs sm:text-[13px] leading-relaxed text-zinc-300">
      {renderBody()}
      <div className="mt-2.5 flex items-center gap-1.5 text-[10px] font-mono text-emerald-400/80">
        <Link2 className="h-3 w-3" />
        Hover or click the highlighted emerald phrase to inspect source proof
      </div>
    </div>
  );
}
