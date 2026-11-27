import { create } from "zustand";
import type {
  EmailDraft,
  ExecutionMode,
  HunterReport,
  ICPProfile,
  LeadRecord,
  LeadSourceType,
  MarketAuditResult,
  PipelinePhase,
  RejectionCategory,
  ResurrectResponse,
  RunStateSnapshot,
  SlayerVerdict,
  StartupInput,
  StreamEvent,
  TelemetryMetrics,
} from "@/types/contracts";

export type ViewTab = "AUDIT" | "BLOODBATH" | "SNIPER";
export type CategoryFilter = RejectionCategory | "ALL" | "SURVIVED";

const DEFAULT_STARTUP_INPUT: StartupInput = {
  product_name: "",
  product_url: "",
  description: "",
  founder_assumptions: "",
  slaying_level: "RUTHLESS",
  execution_mode: "LIVE",
  leads: null,
  lead_sources: ["CSV_PRESET"],
  auto_discover_leads: false,
  target_lead_count: 15,
  target_qualified_leads: 10,
};

interface LeadSlayerState {
  runId: string | null;
  phase: PipelinePhase;
  activeViewTab: ViewTab;
  executionMode: ExecutionMode;
  startupInput: StartupInput;
  leadOrder: string[];
  leadsById: Record<string, LeadRecord>;
  marketAudit: MarketAuditResult | null;
  icps: ICPProfile[];
  hunterReport: HunterReport | null;
  verdictsById: Record<string, SlayerVerdict>;
  emailsById: Record<string, EmailDraft>;
  telemetry: TelemetryMetrics | null;
  selectedLeadId: string | null;
  activeCategoryFilter: CategoryFilter;
  agentLogs: string[];
  errorMessage: string | null;
  isLoadingPreset: boolean;
  isStartingRun: boolean;

  setExecutionMode: (mode: ExecutionMode) => void;
  updateStartupInput: (patch: Partial<StartupInput>) => void;
  setIsLoadingPreset: (loading: boolean) => void;
  setIsStartingRun: (starting: boolean) => void;
  setPresetData: (startup: StartupInput, leads: LeadRecord[]) => void;
  setCustomLeads: (leads: LeadRecord[]) => void;
  setLeadSources: (sources: LeadSourceType[]) => void;
  enableAutoDiscovery: () => void;
  beginRun: (runId: string) => void;
  setActiveViewTab: (tab: ViewTab) => void;
  setSelectedLeadId: (leadId: string | null) => void;
  setActiveCategoryFilter: (filter: CategoryFilter) => void;
  toggleEmailApproval: (leadId: string) => void;
  applyStreamEvent: (event: StreamEvent) => void;
  hydrateFromSnapshot: (snapshot: RunStateSnapshot) => void;
  applyResurrection: (res: ResurrectResponse) => void;
  markDispatched: (leadIds: string[]) => void;
  setError: (msg: string | null) => void;
  resetDemo: () => void;
}

function indexLeads(leads: LeadRecord[]): {
  leadOrder: string[];
  leadsById: Record<string, LeadRecord>;
} {
  const leadOrder: string[] = [];
  const leadsById: Record<string, LeadRecord> = {};
  for (const lead of leads) {
    leadOrder.push(lead.id);
    leadsById[lead.id] = lead;
  }
  return { leadOrder, leadsById };
}

export const useLeadSlayerStore = create<LeadSlayerState>((set) => ({
  runId: null,
  phase: "IDLE",
  activeViewTab: "AUDIT",
  executionMode: "LIVE",
  startupInput: DEFAULT_STARTUP_INPUT,
  leadOrder: [],
  leadsById: {},
  marketAudit: null,
  icps: [],
  hunterReport: null,
  verdictsById: {},
  emailsById: {},
  telemetry: null,
  selectedLeadId: null,
  activeCategoryFilter: "ALL",
  agentLogs: [],
  errorMessage: null,
  isLoadingPreset: false,
  isStartingRun: false,

  setExecutionMode: (mode) =>
    set((s) => ({
      executionMode: mode,
      startupInput: { ...s.startupInput, execution_mode: mode },
    })),

  updateStartupInput: (patch) =>
    set((s) => ({
      startupInput: { ...s.startupInput, ...patch },
    })),

  setIsLoadingPreset: (loading) => set({ isLoadingPreset: loading }),
  setIsStartingRun: (starting) => set({ isStartingRun: starting }),

  setPresetData: (startup, leads) => {
    const { leadOrder, leadsById } = indexLeads(leads);
    set((s) => ({
      startupInput: {
        ...startup,
        execution_mode: s.executionMode,
        leads,
        lead_sources: ["CSV_PRESET"],
        auto_discover_leads: false,
      },
      leadOrder,
      leadsById,
      errorMessage: null,
    }));
  },

  setCustomLeads: (leads) => {
    const { leadOrder, leadsById } = indexLeads(leads);
    set((s) => {
      const current = s.startupInput.lead_sources ?? ["CSV_PRESET"];
      const nextSources: LeadSourceType[] = current.includes("CSV_PRESET")
        ? current
        : [...current, "CSV_PRESET"];
      return {
        startupInput: {
          ...s.startupInput,
          leads,
          lead_sources: nextSources,
          auto_discover_leads: nextSources.some((x) => x !== "CSV_PRESET"),
        },
        leadOrder,
        leadsById,
        errorMessage: null,
      };
    });
  },

  setLeadSources: (sources) =>
    set((s) => {
      const clean: LeadSourceType[] = sources.length > 0 ? sources : ["AI_SEARCH"];
      const usesCsv = clean.includes("CSV_PRESET");
      const usesAuto = clean.some((x) => x === "AI_SEARCH" || x === "LINKEDIN_SEARCH");
      return {
        startupInput: {
          ...s.startupInput,
          lead_sources: clean,
          auto_discover_leads: usesAuto,
          leads: usesCsv ? s.startupInput.leads : null,
          target_lead_count: s.startupInput.target_lead_count ?? 15,
        },
        leadOrder: usesCsv ? s.leadOrder : [],
        leadsById: usesCsv ? s.leadsById : {},
        errorMessage: null,
      };
    }),

  enableAutoDiscovery: () =>
    set((s) => ({
      startupInput: {
        ...s.startupInput,
        leads: null,
        lead_sources: ["AI_SEARCH", "LINKEDIN_SEARCH"],
        auto_discover_leads: true,
        target_lead_count: s.startupInput.target_lead_count ?? 15,
      },
      leadOrder: [],
      leadsById: {},
      errorMessage: null,
    })),

  beginRun: (runId) =>
    set({
      runId,
      phase: "AUDITING",
      activeViewTab: "AUDIT",
      marketAudit: null,
      icps: [],
      hunterReport: null,
      verdictsById: {},
      emailsById: {},
      telemetry: null,
      selectedLeadId: null,
      activeCategoryFilter: "ALL",
      agentLogs: [],
      errorMessage: null,
      isStartingRun: false,
    }),

  setActiveViewTab: (tab) => set({ activeViewTab: tab }),
  setSelectedLeadId: (leadId) => set({ selectedLeadId: leadId }),
  setActiveCategoryFilter: (filter) => set({ activeCategoryFilter: filter }),

  toggleEmailApproval: (leadId) =>
    set((s) => {
      const existing = s.emailsById[leadId];
      if (!existing || existing.status === "SENT") return s;
      return {
        emailsById: {
          ...s.emailsById,
          [leadId]: { ...existing, approved: !existing.approved },
        },
      };
    }),

  applyStreamEvent: (event) =>
    set((s) => {
      switch (event.event_type) {
        case "phase_changed": {
          const nextPhase = event.payload.phase;
          let nextTab = s.activeViewTab;
          if (nextPhase === "AUDITING" || nextPhase === "ICP_GENERATION") {
            nextTab = "AUDIT";
          } else if (nextPhase === "HUNTING" || nextPhase === "SLAYING") {
            nextTab = "BLOODBATH";
          } else if (nextPhase === "SNIPING") {
            nextTab = "SNIPER";
          }
          return {
            phase: nextPhase,
            activeViewTab: nextTab,
            telemetry: event.payload.telemetry ?? s.telemetry,
          };
        }

        case "agent_log": {
          const updatedLogs = [...s.agentLogs, event.payload.message].slice(-40);
          return { agentLogs: updatedLogs };
        }

        case "audit_completed":
          return {
            marketAudit: event.payload.audit,
            telemetry: event.payload.telemetry ?? s.telemetry,
          };

        case "icps_generated":
          return {
            icps: event.payload.icps,
            telemetry: event.payload.telemetry ?? s.telemetry,
          };

        case "hunter_report":
          return {
            hunterReport: event.payload.hunter_report,
            telemetry: event.payload.telemetry ?? s.telemetry,
          };

        case "leads_loaded": {
          const { leadOrder, leadsById } = indexLeads(event.payload.leads);
          return {
            leadOrder,
            leadsById,
            telemetry: event.payload.telemetry ?? s.telemetry,
          };
        }

        case "lead_verdict": {
          const verdict = event.payload.verdict;
          return {
            verdictsById: {
              ...s.verdictsById,
              [verdict.lead_id]: verdict,
            },
            telemetry: event.payload.telemetry,
          };
        }

        case "email_drafted": {
          const draft = event.payload.email_draft;
          return {
            emailsById: {
              ...s.emailsById,
              [draft.lead_id]: draft,
            },
            telemetry: event.payload.telemetry ?? s.telemetry,
          };
        }

        case "telemetry_update":
          return { telemetry: event.payload.telemetry };

        case "pipeline_completed":
          return {
            phase: event.payload.phase,
            telemetry: event.payload.telemetry,
          };

        case "pipeline_error":
          return {
            phase: "ERROR",
            errorMessage: event.payload.message,
            isStartingRun: false,
          };

        default:
          return s;
      }
    }),

  hydrateFromSnapshot: (snapshot) => {
    const { leadOrder, leadsById } = indexLeads(snapshot.leads);
    let nextTab: ViewTab = "AUDIT";
    if (snapshot.phase === "HUNTING" || snapshot.phase === "SLAYING") {
      nextTab = "BLOODBATH";
    } else if (
      snapshot.phase === "SNIPING" ||
      snapshot.phase === "READY" ||
      snapshot.phase === "DISPATCHED"
    ) {
      nextTab = "SNIPER";
    }

    set({
      runId: snapshot.run_id,
      phase: snapshot.phase,
      activeViewTab: nextTab,
      startupInput: snapshot.startup_input,
      marketAudit: snapshot.market_audit,
      icps: snapshot.icps,
      hunterReport: snapshot.hunter_report,
      leadOrder,
      leadsById,
      verdictsById: snapshot.verdicts,
      emailsById: snapshot.emails,
      telemetry: snapshot.telemetry,
      errorMessage: snapshot.error_message,
    });
  },

  applyResurrection: (res) =>
    set((s) => ({
      verdictsById: {
        ...s.verdictsById,
        [res.verdict.lead_id]: res.verdict,
      },
      emailsById: {
        ...s.emailsById,
        [res.email_draft.lead_id]: res.email_draft,
      },
      telemetry: res.telemetry,
    })),

  markDispatched: (leadIds) =>
    set((s) => {
      const nextEmails = { ...s.emailsById };
      for (const id of leadIds) {
        if (nextEmails[id]) {
          nextEmails[id] = { ...nextEmails[id], status: "SENT", approved: true };
        }
      }
      return {
        emailsById: nextEmails,
        phase: leadIds.length > 0 ? "DISPATCHED" : s.phase,
      };
    }),

  setError: (msg) => set({ errorMessage: msg }),

  resetDemo: () =>
    set({
      runId: null,
      phase: "IDLE",
      activeViewTab: "AUDIT",
      marketAudit: null,
      icps: [],
      hunterReport: null,
      verdictsById: {},
      emailsById: {},
      telemetry: null,
      selectedLeadId: null,
      activeCategoryFilter: "ALL",
      agentLogs: [],
      errorMessage: null,
      isStartingRun: false,
    }),
}));
