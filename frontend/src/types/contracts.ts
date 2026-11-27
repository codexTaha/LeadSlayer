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
  | "hunter_report"
  | "leads_loaded"
  | "lead_verdict"
  | "email_drafted"
  | "mcp_tool_call"
  | "telemetry_update"
  | "pipeline_completed"
  | "pipeline_error";

export type LeadSourceType = "AI_SEARCH" | "LINKEDIN_SEARCH" | "CSV_PRESET";
export type DeliveryMode = "SANDBOX" | "SMTP" | "GMAIL_OAUTH";

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
  linkedin_url?: string;
  email_status?: string;
  mx_provider?: string;
  source_channel?: string;
}

export interface StartupInput {
  product_name: string;
  product_url: string | null;
  description: string;
  founder_assumptions: string;
  slaying_level: SlayingLevel;
  execution_mode: ExecutionMode;
  leads: LeadRecord[] | null;
  lead_sources?: LeadSourceType[];
  auto_discover_leads?: boolean;
  target_lead_count?: number;
  target_qualified_leads?: number;
}

export interface AssumptionGap {
  founder_belief: string;
  market_reality: string;
  severity: "HIGH" | "MEDIUM" | "LOW";
  strategic_fix: string;
}

export interface CompetitorInsight {
  name: string;
  positioning_weakness: string;
  switching_trigger: string;
}

export interface BuyingObjection {
  objection: string;
  buyer_role: string;
  counter_angle: string;
}

export interface ReadinessBreakdown {
  pain_urgency: number;
  icp_clarity: number;
  differentiation: number;
  timing_fit: number;
}

export interface MarketAuditResult {
  market_reality_summary: string;
  founder_blind_spots: string[];
  sharpened_value_prop: string;
  anti_icp_red_flags: string[];
  market_readiness_score: number;
  url_scraped_context_used: boolean;
  search_grounding_used: boolean;
  assumption_gaps: AssumptionGap[];
  competitor_landscape: CompetitorInsight[];
  buying_objections: BuyingObjection[];
  readiness_breakdown: ReadinessBreakdown | null;
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

export interface HuntQuery {
  source: string;
  query_string: string;
  signal_target: string;
}

export interface HunterReport {
  hunt_queries: HuntQuery[];
  enriched_sparse_leads: number;
  url_fetches_succeeded: number;
  total_leads_ready: number;
  autonomous_discovered_leads?: number;
  discovery_sources?: string[];
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

export interface MCPToolCallRecord {
  id: string;
  timestamp_ms: number;
  agent_name: string;
  decision_reason: string;
  server_name: string;
  tool_name: string;
  arguments_summary: string;
  result_summary: string;
  status: "CALLED" | "SUCCEEDED" | "BLOCKED" | "FAILED";
}

export interface MCPStatusResponse {
  connected: boolean;
  server_name: string;
  transport: string;
  tools: string[];
  error: string;
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
      event_type: "hunter_report";
      payload: { hunter_report: HunterReport; telemetry?: TelemetryMetrics };
    }
  | {
      event_id: number;
      run_id: string;
      timestamp_ms: number;
      event_type: "leads_loaded";
      payload: { leads: LeadRecord[]; telemetry?: TelemetryMetrics };
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
      event_type: "mcp_tool_call";
      payload: { mcp_tool_call: MCPToolCallRecord; telemetry?: TelemetryMetrics };
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
  hunter_report: HunterReport | null;
  leads: LeadRecord[];
  verdicts: Record<string, SlayerVerdict>;
  emails: Record<string, EmailDraft>;
  mcp_tool_calls?: MCPToolCallRecord[];
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
  delivery_mode?: DeliveryMode;
}

export interface DispatchReceipt {
  lead_id: string;
  recipient_email: string;
  status: "SENT" | "BLOCKED" | "FAILED";
  provider?: string;
  message_id?: string;
  gate_reasons?: string[];
  error?: string;
}

export interface DispatchResponse {
  dispatched_count: number;
  blocked_count?: number;
  delivery_mode?: string;
  sent_at: string;
  receipts: DispatchReceipt[];
}

export interface MailStatusResponse {
  mail_engine_ready: boolean;
  smtp_configured: boolean;
  gmail_configured: boolean;
  gmail_oauth_available: boolean;
  linkedin_browser_configured: boolean;
  active_provider: "SANDBOX" | "SMTP" | "GMAIL_OAUTH";
  smtp_sender: string;
  sender_name: string;
  do_not_contact_count: number;
}

export interface SMTPConnectRequest {
  email: string;
  password: string;
  smtp_host: string;
  smtp_port: number;
  sender_name: string;
  postal_address?: string;
  verify_connection?: boolean;
}
