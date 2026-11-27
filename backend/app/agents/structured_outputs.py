from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

from app.models.schemas import HuntQuery, ICPProfile, RejectionCategory


class ICPBatchOutput(BaseModel):
    icps: list[ICPProfile] = Field(min_length=1, max_length=3)


class HuntQueriesOutput(BaseModel):
    hunt_queries: list[HuntQuery] = Field(min_length=1, max_length=5)


class EnrichedLeadPatch(BaseModel):
    lead_id: str
    inferred_tech_stack: list[str] = Field(default_factory=list)
    inferred_signal: str = ""


class EnrichedLeadBatch(BaseModel):
    patches: list[EnrichedLeadPatch] = Field(default_factory=list)


class DiscoveredLeadCandidate(BaseModel):
    full_name: str
    role: str
    company: str
    domain: str
    industry: str
    employee_count: int = Field(ge=1)
    funding_stage: str
    tech_stack: list[str] = Field(default_factory=list)
    recent_signal: str
    bio_snippet: str
    email_guess: str = ""
    linkedin_url: str = ""


class DiscoveredLeadBatch(BaseModel):
    candidates: list[DiscoveredLeadCandidate] = Field(default_factory=list)


class SlayerLLMResponse(BaseModel):
    """
    Think-first field ordering forces the model to extract red-flag evidence
    and classify the tier BEFORE committing to survived=True/False.
    """

    disqualifier_signals_found: list[str] = Field(default_factory=list)
    tier_triggered: Literal["NONE", "TIER_1_HARD", "TIER_2_ICP_FIT", "TIER_3_FRICTION"]
    rejection_category: RejectionCategory | None = None
    reasoning: str
    survived: bool
    headline_tag: str
    confidence: float = Field(ge=0.0, le=1.0)


class SlayerBatchItem(SlayerLLMResponse):
    lead_id: str


class SlayerBatchLLMResponse(BaseModel):
    verdicts: list[SlayerBatchItem]


class SniperLLMResponse(BaseModel):
    cited_survival_signal: str
    subject: str
    body: str
    email_evidence_phrase: str
    personalization_score: int = Field(ge=0, le=100)


class SniperBatchItem(SniperLLMResponse):
    lead_id: str


class SniperBatchLLMResponse(BaseModel):
    drafts: list[SniperBatchItem]
