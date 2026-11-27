from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


class SlayingLevel(str, Enum):
    LENIENT = "LENIENT"
    NORMAL = "NORMAL"
    RUTHLESS = "RUTHLESS"


class ExecutionMode(str, Enum):
    LIVE = "LIVE"
    SAFE_REPLAY = "SAFE_REPLAY"


class PipelinePhase(str, Enum):
    IDLE = "IDLE"
    AUDITING = "AUDITING"
    ICP_GENERATION = "ICP_GENERATION"
    HUNTING = "HUNTING"
    SLAYING = "SLAYING"
    SNIPING = "SNIPING"
    READY = "READY"
    DISPATCHED = "DISPATCHED"
    ERROR = "ERROR"


class RejectionCategory(str, Enum):
    COMPETITOR_LOCK_IN = "COMPETITOR_LOCK_IN"
    TOO_SMALL = "TOO_SMALL"
    LAYOFFS_FREEZE = "LAYOFFS_FREEZE"
    WRONG_PERSONA = "WRONG_PERSONA"
    NO_STACK_FIT = "NO_STACK_FIT"
    BUILT_IN_HOUSE = "BUILT_IN_HOUSE"
    NO_URGENCY_SIGNAL = "NO_URGENCY_SIGNAL"


class ModelId(str, Enum):
    GEMINI_4_HYDROGEN = "gemini-4-hydrogen"
    GEMINI_3_5_FLASH_LITE = "gemini-3.5-flash-lite"
    GEMINI_EMBEDDING_2 = "gemini-embedding-2"


class StreamEventType(str, Enum):
    PHASE_CHANGED = "phase_changed"
    AGENT_LOG = "agent_log"
    AUDIT_COMPLETED = "audit_completed"
    ICPS_GENERATED = "icps_generated"
    HUNTER_REPORT = "hunter_report"
    LEADS_LOADED = "leads_loaded"
    LEAD_VERDICT = "lead_verdict"
    EMAIL_DRAFTED = "email_drafted"
    TELEMETRY_UPDATE = "telemetry_update"
    PIPELINE_COMPLETED = "pipeline_completed"
    PIPELINE_ERROR = "pipeline_error"


FundingStage = Literal[
    "Bootstrapped",
    "Pre-Seed",
    "Seed",
    "Series A",
    "Series B",
    "Series C",
    "Public",
]

LeadSourceType = Literal["AI_SEARCH", "LINKEDIN_SEARCH", "CSV_PRESET"]


class LeadRecord(BaseModel):
    id: str = Field(min_length=1)
    full_name: str = Field(min_length=1)
    role: str = Field(min_length=1)
    company: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    industry: str = Field(min_length=1)
    employee_count: int = Field(ge=1)
    funding_stage: str = Field(min_length=1)
    tech_stack: list[str] = Field(default_factory=list)
    recent_signal: str = Field(default="")
    bio_snippet: str = Field(default="")
    email: str = Field(min_length=3)
    linkedin_url: str = Field(default="")
    email_status: str = Field(default="unknown")
    mx_provider: str = Field(default="")
    source_channel: str = Field(default="CSV")


class StartupInput(BaseModel):
    product_name: str = Field(min_length=2)
    product_url: str | None = None
    description: str = Field(min_length=20)
    founder_assumptions: str = Field(min_length=5)
    slaying_level: SlayingLevel = SlayingLevel.RUTHLESS
    execution_mode: ExecutionMode = ExecutionMode.LIVE
    leads: list[LeadRecord] | None = None
    lead_sources: list[LeadSourceType] = Field(default_factory=lambda: ["CSV_PRESET"])
    auto_discover_leads: bool = False
    target_lead_count: int = Field(default=15, ge=5, le=30)
    # How many QUALIFIED survivors the loop must reach before stopping (1–50).
    target_qualified_leads: int = Field(default=10, ge=1, le=50)


class AssumptionGap(BaseModel):
    founder_belief: str
    market_reality: str
    severity: Literal["HIGH", "MEDIUM", "LOW"] = "HIGH"
    strategic_fix: str


class CompetitorInsight(BaseModel):
    name: str
    positioning_weakness: str
    switching_trigger: str


class BuyingObjection(BaseModel):
    objection: str
    buyer_role: str
    counter_angle: str


class ReadinessBreakdown(BaseModel):
    pain_urgency: int = Field(ge=0, le=100)
    icp_clarity: int = Field(ge=0, le=100)
    differentiation: int = Field(ge=0, le=100)
    timing_fit: int = Field(ge=0, le=100)


class MarketAuditResult(BaseModel):
    market_reality_summary: str
    founder_blind_spots: list[str] = Field(min_length=1)
    sharpened_value_prop: str
    anti_icp_red_flags: list[str] = Field(min_length=1)
    market_readiness_score: int = Field(ge=0, le=100)
    url_scraped_context_used: bool = False
    search_grounding_used: bool = False
    assumption_gaps: list[AssumptionGap] = Field(default_factory=list)
    competitor_landscape: list[CompetitorInsight] = Field(default_factory=list)
    buying_objections: list[BuyingObjection] = Field(default_factory=list)
    readiness_breakdown: ReadinessBreakdown | None = None


class ICPProfile(BaseModel):
    id: str
    name: str
    target_roles: list[str]
    min_employees: int = Field(ge=1)
    max_employees: int = Field(ge=1)
    required_tech_signals: list[str]
    buying_triggers: list[str]
    instant_disqualifiers: list[str]
    vector_doc_id: str


class HuntQuery(BaseModel):
    source: str
    query_string: str
    signal_target: str


class HunterReport(BaseModel):
    hunt_queries: list[HuntQuery] = Field(default_factory=list)
    enriched_sparse_leads: int = 0
    url_fetches_succeeded: int = 0
    total_leads_ready: int = 0
    autonomous_discovered_leads: int = 0
    discovery_sources: list[str] = Field(default_factory=list)


class SlayerVerdict(BaseModel):
    lead_id: str
    survived: bool
    resurrected_by_user: bool = False
    rejection_category: RejectionCategory | None = None
    headline_tag: str
    reasoning: str
    matched_icp_id: str | None = None
    icp_similarity_score: float = Field(ge=0.0, le=1.0)
    anti_icp_similarity_score: float = Field(ge=0.0, le=1.0)
    structural_match_score: float = Field(ge=0.0, le=1.0)
    qualification_score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0.0, le=1.0)
    slaying_level_applied: SlayingLevel
    latency_ms: int = Field(ge=0)
    model_used: ModelId = ModelId.GEMINI_3_5_FLASH_LITE

    @model_validator(mode="after")
    def validate_rejection_category(self) -> "SlayerVerdict":
        if not self.survived and self.rejection_category is None:
            raise ValueError("rejection_category is required when survived is False")
        return self


class EmailDraft(BaseModel):
    lead_id: str
    recipient_name: str
    recipient_email: str
    company: str
    subject: str
    body: str
    cited_survival_signal: str
    email_evidence_phrase: str
    matched_product_chunk: str
    personalization_score: int = Field(ge=0, le=100)
    approved: bool = True
    status: Literal["DRAFTED", "SENT"] = "DRAFTED"


class TelemetryMetrics(BaseModel):
    total_leads: int = 0
    processed_leads: int = 0
    killed_count: int = 0
    survived_count: int = 0
    kill_rate_pct: float = 0.0
    rejection_breakdown: dict[str, int] = Field(default_factory=dict)
    model_calls: dict[str, int] = Field(default_factory=dict)
    avg_slayer_latency_ms: float = 0.0
    elapsed_ms: int = 0
    estimated_saved_spam_hours: float = 0.0


class StreamEvent(BaseModel):
    event_id: int = Field(ge=1)
    run_id: str
    timestamp_ms: int
    event_type: StreamEventType
    payload: dict[str, Any] = Field(default_factory=dict)


class RunStateSnapshot(BaseModel):
    run_id: str
    phase: PipelinePhase
    startup_input: StartupInput
    market_audit: MarketAuditResult | None = None
    icps: list[ICPProfile] = Field(default_factory=list)
    hunter_report: HunterReport | None = None
    leads: list[LeadRecord] = Field(default_factory=list)
    verdicts: dict[str, SlayerVerdict] = Field(default_factory=dict)
    emails: dict[str, EmailDraft] = Field(default_factory=dict)
    telemetry: TelemetryMetrics = Field(default_factory=TelemetryMetrics)
    error_message: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    models: dict[str, str]
    default_demo_ready: bool


class PresetResponse(BaseModel):
    startup: StartupInput
    leads: list[LeadRecord]


class ParseCsvResponse(BaseModel):
    count: int
    leads: list[LeadRecord]
    warnings: list[str] = Field(default_factory=list)


class PipelineStartResponse(BaseModel):
    run_id: str
    stream_url: str


class ResurrectResponse(BaseModel):
    verdict: SlayerVerdict
    email_draft: EmailDraft
    telemetry: TelemetryMetrics


DeliveryMode = Literal["SANDBOX", "HARVEY_SMTP", "HARVEY_GMAIL"]


class DispatchRequest(BaseModel):
    lead_ids: list[str]
    delivery_mode: DeliveryMode = "SANDBOX"


class DispatchReceipt(BaseModel):
    lead_id: str
    recipient_email: str
    status: Literal["SENT", "BLOCKED", "FAILED"] = "SENT"
    provider: str = "SANDBOX"
    message_id: str = ""
    gate_reasons: list[str] = Field(default_factory=list)
    error: str = ""


class DispatchResponse(BaseModel):
    dispatched_count: int
    blocked_count: int = 0
    delivery_mode: str = "SANDBOX"
    sent_at: str
    receipts: list[DispatchReceipt]


class HarveyStatusResponse(BaseModel):
    harvey_connected: bool
    smtp_configured: bool
    gmail_configured: bool
    linkedin_playwright_configured: bool
    smtp_sender: str = ""
    do_not_contact_count: int = 0
