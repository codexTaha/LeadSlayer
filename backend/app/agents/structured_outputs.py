from typing import Literal
from pydantic import BaseModel, Field, field_validator

from app.models.schemas import ICPProfile, RejectionCategory


class _ICPBatchOutput(BaseModel):
    icps: list[ICPProfile] = Field(description="Exactly 3 diverse and actionable ICP profiles")

    @field_validator("icps")
    @classmethod
    def validate_exactly_three_icps(cls, v: list[ICPProfile]) -> list[ICPProfile]:
        if len(v) != 3:
            raise ValueError(f"Expected exactly 3 ICP profiles, got {len(v)}")
        return v


class _EnrichedLeadPatch(BaseModel):
    lead_id: str
    inferred_tech_stack: list[str] = Field(default_factory=list)
    inferred_signal: str = Field(default="")


class _SlayerLLMResponse(BaseModel):
    """
    CRITICAL FIELD ORDER:
    Disqualifier signals and tier must be evaluated FIRST to force the model to reason
    adversarially before making the survival verdict.
    """
    disqualifier_signals_found: list[str] = Field(
        description="List of specific anti-ICP red flags or disqualifier facts found in this lead"
    )
    tier_triggered: Literal["NONE", "TIER_1_HARD", "TIER_2_ICP_FIT", "TIER_3_FRICTION"] = Field(
        description="The disqualification tier triggered, or NONE if lead qualifies cleanly"
    )
    rejection_category: RejectionCategory | None = Field(
        default=None,
        description="Required if survived is False. Must be None if survived is True."
    )
    reasoning: str = Field(
        description="1-2 sentences citing exact facts from the lead explaining kill or survival"
    )
    survived: bool = Field(
        description="True ONLY if the lead passes all qualification filters for the active mode"
    )
    headline_tag: str = Field(
        description="Punchy tag up to 5 words starting with 'KILLED: ' or 'SURVIVED: '"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in this verdict between 0.0 and 1.0"
    )


class _SniperLLMResponse(BaseModel):
    cited_survival_signal: str = Field(
        description="The specific lead trigger or tech signal that justified survival"
    )
    subject: str = Field(
        description="Technical peer subject line (max 9 words, no marketing buzzwords)"
    )
    body: str = Field(
        description="High-context cold email body (75-130 words, peer-to-peer tone)"
    )
    email_evidence_phrase: str = Field(
        description="CRITICAL: Verbatim substring copied directly from inside body"
    )
    personalization_score: int = Field(
        ge=0,
        le=100,
        description="Quality rating of signal-to-product mapping (0-100)"
    )
