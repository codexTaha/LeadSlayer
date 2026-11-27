from typing import Protocol
from pydantic import BaseModel

from app.models.schemas import (
    EmailDraft,
    HunterReport,
    ICPProfile,
    LeadRecord,
    MarketAuditResult,
    ModelId,
    PipelinePhase,
    SlayerVerdict,
)


class PipelineCallbacks(Protocol):
    async def on_phase(self, phase: PipelinePhase) -> None: ...
    async def on_log(self, message: str) -> None: ...
    async def on_model_call(self, model_id: ModelId) -> None: ...
    async def on_audit(self, audit: MarketAuditResult) -> None: ...
    async def on_icps(self, icps: list[ICPProfile]) -> None: ...
    async def on_leads_loaded(self, leads: list[LeadRecord]) -> None: ...
    async def on_hunter_report(self, report: HunterReport) -> None: ...
    async def on_verdict(self, verdict: SlayerVerdict) -> None: ...
    async def on_email(self, draft: EmailDraft) -> None: ...


class PipelineFinalResult(BaseModel):
    run_id: str
    market_audit: MarketAuditResult
    icps: list[ICPProfile]
    hunter_report: HunterReport | None = None
    verdicts: dict[str, SlayerVerdict]
    emails: dict[str, EmailDraft]
