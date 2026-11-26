from typing import Protocol
from pydantic import BaseModel

from app.models.schemas import (
    EmailDraft,
    ICPProfile,
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
    async def on_verdict(self, verdict: SlayerVerdict) -> None: ...
    async def on_email(self, draft: EmailDraft) -> None: ...


class PipelineFinalResult(BaseModel):
    run_id: str
    market_audit: MarketAuditResult
    icps: list[ICPProfile]
    verdicts: dict[str, SlayerVerdict]
    emails: dict[str, EmailDraft]
