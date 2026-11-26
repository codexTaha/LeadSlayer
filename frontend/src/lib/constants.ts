import type {
  PipelinePhase,
  RejectionCategory,
  SlayingLevel,
} from "@/types/contracts";

export interface SlayingLevelMeta {
  level: SlayingLevel;
  label: string;
  tagline: string;
  expectedSurvival: string;
  accentText: string;
  accentBorder: string;
  accentBg: string;
}

export const SLAYING_LEVELS: Record<SlayingLevel, SlayingLevelMeta> = {
  LENIENT: {
    level: "LENIENT",
    label: "Scout",
    tagline: "Kills hard blockers only; borderline prospects survive",
    expectedSurvival: "~36% survive",
    accentText: "text-amber-400",
    accentBorder: "border-amber-500/60",
    accentBg: "bg-amber-500/10",
  },
  NORMAL: {
    level: "NORMAL",
    label: "Tactical",
    tagline: "Balanced ICP, stack, and budget velocity triage",
    expectedSurvival: "~24% survive",
    accentText: "text-orange-400",
    accentBorder: "border-orange-500/60",
    accentBg: "bg-orange-500/10",
  },
  RUTHLESS: {
    level: "RUTHLESS",
    label: "Bloodbath",
    tagline: "Zero mercy. Protect sender domain at all costs",
    expectedSurvival: "~16% survive",
    accentText: "text-rose-400",
    accentBorder: "border-rose-500/70",
    accentBg: "bg-rose-500/15",
  },
};

export const REJECTION_CATEGORY_LABELS: Record<RejectionCategory, string> = {
  COMPETITOR_LOCK_IN: "Competitor Lock-In",
  TOO_SMALL: "Too Small",
  LAYOFFS_FREEZE: "Layoffs / Freeze",
  WRONG_PERSONA: "Wrong Persona",
  NO_STACK_FIT: "No Stack Fit",
  BUILT_IN_HOUSE: "Built In-House",
  NO_URGENCY_SIGNAL: "No Urgency",
};

export const PHASE_STEP_ORDER: {
  id: string;
  label: string;
  phases: PipelinePhase[];
  viewTab: "AUDIT" | "BLOODBATH" | "SNIPER";
}[] = [
  {
    id: "audit",
    label: "1. Market Audit",
    phases: ["AUDITING"],
    viewTab: "AUDIT",
  },
  {
    id: "icp",
    label: "2. ICP & Memory",
    phases: ["ICP_GENERATION"],
    viewTab: "AUDIT",
  },
  {
    id: "hunter",
    label: "3. Hunter Swarm",
    phases: ["HUNTING"],
    viewTab: "BLOODBATH",
  },
  {
    id: "slayer",
    label: "4. The Bloodbath",
    phases: ["SLAYING"],
    viewTab: "BLOODBATH",
  },
  {
    id: "sniper",
    label: "5. Sniper Deck",
    phases: ["SNIPING", "READY", "DISPATCHED"],
    viewTab: "SNIPER",
  },
];
