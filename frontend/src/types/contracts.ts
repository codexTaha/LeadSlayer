// Strict 1:1 TypeScript mirror of backend/app/models/schemas.py

export type SlayingLevel = "LENIENT" | "NORMAL" | "RUTHLESS";

export type ExecutionMode = "LIVE" | "SAFE_REPLAY";

export type PipelinePhase =
  | "IDLE"
  | "AUDITING"
  | "ICP_GENERATION"
  | "HUNTING"
  | "SLAYING"
  | "SNIPING"
  | "READY"
  | "DISPATCHED"
  | "ERROR";

export type RejectionCategory =
  | "COMPETITOR_LOCK_IN"
  | "TOO_SMALL"
  | "LAYOFFS_FREEZE"
  | "WRONG_PERSONA"
  | "NO_STACK_FIT"
  | "BUILT_IN_HOUSE"
  | "NO_URGENCY_SIGNAL";

export type ModelId =
  | "gemini-4-hydrogen"
  | "gemini-3.5-flash-lite"
  | "gemini-embedding-2";

export type StreamEventType =
  | "phase_changed"
  | "agent_log"
  | "audit_completed"
  | "icps_generated"
  | "leads_loaded"
  | "lead_verdict"
  | "email_drafted"
  | "telemetry_update"
  | "pipeline_completed"
  | "pipeline_error";

export interface LeadRecord {
  id: string;
  full_name: string;
  role: string;
  company: string;
  domain: string;
  industry: string;
  employee_count: number;
  funding_stage: string;
  tech_stack: string[];
  recent_signal: string;
  bio_snippet: string;
  email: string;
}

export interface StartupInput {
  product_name: string;
  product_url: string | null;
  description: string;
  founder_assumptions: string;
  slaying_level: SlayingLevel;
  execution_mode: ExecutionMode;
  leads: LeadRecord[] | null;
}

export interface MarketAuditResult {
  market_reality_summary: string;
  founder_blind_spots: string[];
  sharpened_value_prop: string;
  anti_icp_red_flags: string[];
  market_readiness_score: number;
}

export interface ICPProfile {
  id: string;
  name: string;
  target_roles: string[];
  min_employees: number;
  max_employees: number;
  required_tech_signals: string[];
  buying_triggers: string[];
  instant_disqualifiers: string[];
  vector_doc_id: string;
}

export interface SlayerVerdict {
  lead_id: string;
  survived: boolean;
  resurrected_by_user: boolean;
  rejection_category: RejectionCategory | null;
  headline_tag: string;
  reasoning: string;
  matched_icp_id: string | null;
  icp_similarity_score: number;
  anti_icp_similarity_score: number;
  structural_match_score: number;
  qualification_score: number;
  confidence: number;
  slaying_level_applied: SlayingLevel;
  latency_ms: number;
  model_used: ModelId;
}

export interface EmailDraft {
  lead_id: string;
  recipient_name: string;
  recipient_email: string;
  company: string;
  subject: string;
  body: string;
  cited_survival_signal: string;
  email_evidence_phrase: string;
  matched_product_chunk: string;
  personalization_score: number;
  approved: boolean;
  status: "DRAFTED" | "SENT";
}

export interface TelemetryMetrics {
  total_leads: number;
  processed_leads: number;
  killed_count: number;
  survived_count: number;
  kill_rate_pct: number;
  rejection_breakdown: Record<string, number>;
  model_calls: Record<string, number>;
  avg_slayer_latency_ms: number;
  elapsed_ms: number;
  estimated_saved_spam_hours: number;
}

export type StreamEvent =
  | {
      event_id: number;
      run_id: string;
      timestamp_ms: number;
      event_type: "phase_changed";
      payload: { phase: PipelinePhase; telemetry?: TelemetryMetrics };
    }
  | {
      event_id: number;
      run_id: string;
      timestamp_ms: number;
      event_type: "agent_log";
      payload: { message: string };
    }
  | {
      event_id: number;
      run_id: string;
      timestamp_ms: number;
      event_type: "audit_completed";
      payload: { audit: MarketAuditResult; telemetry?: TelemetryMetrics };
    }
  | {
      event_id: number;
      run_id: string;
      timestamp_ms: number;
      event_type: "icps_generated";
      payload: { icps: ICPProfile[]; telemetry?: TelemetryMetrics };
    }
  | {
      event_id: number;
      run_id: string;
      timestamp_ms: number;
      event_type: "leads_loaded";
      payload: { leads: LeadRecord[] };
    }
  | {
      event_id: number;
      run_id: string;
      timestamp_ms: number;
      event_type: "lead_verdict";
      payload: { verdict: SlayerVerdict; telemetry: TelemetryMetrics };
    }
  | {
      event_id: number;
      run_id: string;
      timestamp_ms: number;
      event_type: "email_drafted";
      payload: { email_draft: EmailDraft; telemetry?: TelemetryMetrics };
    }
  | {
      event_id: number;
      run_id: string;
      timestamp_ms: number;
      event_type: "telemetry_update";
      payload: { telemetry: TelemetryMetrics };
    }
  | {
      event_id: number;
      run_id: string;
      timestamp_ms: number;
      event_type: "pipeline_completed";
      payload: { phase: PipelinePhase; telemetry: TelemetryMetrics };
    }
  | {
      event_id: number;
      run_id: string;
      timestamp_ms: number;
      event_type: "pipeline_error";
      payload: { message: string; status_code?: number | null };
    };

export interface RunStateSnapshot {
  run_id: string;
  phase: PipelinePhase;
  startup_input: StartupInput;
  market_audit: MarketAuditResult | null;
  icps: ICPProfile[];
  leads: LeadRecord[];
  verdicts: Record<string, SlayerVerdict>;
  emails: Record<string, EmailDraft>;
  telemetry: TelemetryMetrics;
  error_message: string | null;
}

export interface HealthResponse {
  status: "ok";
  models: Record<string, string>;
  default_demo_ready: boolean;
}

export interface PresetResponse {
  startup: StartupInput;
  leads: LeadRecord[];
}

export interface ParseCsvResponse {
  count: number;
  leads: LeadRecord[];
  warnings: string[];
}

export interface PipelineStartResponse {
  run_id: string;
  stream_url: string;
}

export interface ResurrectResponse {
  verdict: SlayerVerdict;
  email_draft: EmailDraft;
  telemetry: TelemetryMetrics;
}

export interface DispatchRequest {
  lead_ids: string[];
}

export interface DispatchReceipt {
  lead_id: string;
  recipient_email: string;
  status: "SENT";
}

export interface DispatchResponse {
  dispatched_count: number;
  sent_at: string;
  receipts: DispatchReceipt[];
}
