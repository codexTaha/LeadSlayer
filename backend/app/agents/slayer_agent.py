from __future__ import annotations

import time
from collections.abc import AsyncIterator
from typing import Any

from google import genai
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from pydantic import ConfigDict

from app.agents.interface import PipelineCallbacks
from app.agents.key_rotator import key_rotator
from app.agents.prompts import build_slayer_system_prompt
from app.agents.rate_limiter import GentleAdaptiveExecutor
from app.agents.structured_outputs import SlayerBatchItem, SlayerBatchLLMResponse
from app.config import settings
from app.memory.vector_store import HybridMatchContext
from app.models.schemas import (
    LeadRecord,
    MarketAuditResult,
    ModelId,
    PipelinePhase,
    RejectionCategory,
    SlayerVerdict,
    StartupInput,
)


SLAYER_MICRO_BATCH_SIZE = 10


def _normalize_headline_tag(raw_tag: str, survived: bool) -> str:
    prefix = "SURVIVED:" if survived else "KILLED:"
    cleaned = " ".join(raw_tag.strip().split())
    if not cleaned:
        return f"{prefix} High Fit" if survived else f"{prefix} Disqualified"
    upper = cleaned.upper()
    if upper.startswith("KILLED:") or upper.startswith("SURVIVED:"):
        body = cleaned.split(":", 1)[1].strip()
    else:
        body = cleaned
    words = body.split()[:4]
    return f"{prefix} {' '.join(words)}".strip()


def _fuse_qualification_score(prior_100: int, confidence: float, survived: bool) -> int:
    if survived:
        raw = round(0.40 * prior_100 + 0.60 * (confidence * 100.0))
        return max(65, min(99, raw))
    raw = round(0.40 * prior_100 + 0.60 * ((1.0 - confidence) * 100.0))
    return max(4, min(62, raw))


def _format_lead_for_slayer(lead: LeadRecord, prior: HybridMatchContext) -> str:
    return (
        f"[lead_id={lead.id}]\n"
        f"  Name: {lead.full_name} | Role: {lead.role}\n"
        f"  Company: {lead.company} ({lead.industry}, {lead.employee_count} employees, {lead.funding_stage})\n"
        f"  Tech Stack: {', '.join(lead.tech_stack) or 'None listed'}\n"
        f"  Recent Signal: {lead.recent_signal}\n"
        f"  Bio: {lead.bio_snippet}\n"
        f"  Best ICP: {prior.best_icp.name} (target size {prior.best_icp.min_employees}-{prior.best_icp.max_employees}, "
        f"required stack: {', '.join(prior.best_icp.required_tech_signals)})\n"
        f"  Stage 2 Vector Priors: prior_score_100={prior.prior_score_100}, "
        f"icp_sim={prior.icp_similarity_score}, anti_icp_sim={prior.anti_icp_similarity_score} "
        f"(closest red flag: {prior.matched_anti_icp_rule or 'none'}), structural_fit={prior.structural_match_score}"
    )


def _to_slayer_verdict(
    item: SlayerBatchItem,
    prior: HybridMatchContext,
    startup: StartupInput,
    latency_ms: int,
) -> SlayerVerdict:
    survived = item.survived
    rejection_cat = (
        None
        if survived
        else (item.rejection_category or RejectionCategory.NO_URGENCY_SIGNAL)
    )
    headline = _normalize_headline_tag(item.headline_tag, survived)
    qual_score = _fuse_qualification_score(
        prior.prior_score_100, item.confidence, survived
    )
    return SlayerVerdict(
        lead_id=item.lead_id,
        survived=survived,
        resurrected_by_user=False,
        rejection_category=rejection_cat,
        headline_tag=headline,
        reasoning=item.reasoning,
        matched_icp_id=prior.best_icp.id if survived else None,
        icp_similarity_score=prior.icp_similarity_score,
        anti_icp_similarity_score=prior.anti_icp_similarity_score,
        structural_match_score=prior.structural_match_score,
        qualification_score=qual_score,
        confidence=item.confidence,
        slaying_level_applied=startup.slaying_level,
        latency_ms=latency_ms,
        model_used=ModelId.GEMINI_3_5_FLASH_LITE,
    )


async def execute_slayer_swarm(
    startup: StartupInput,
    audit: MarketAuditResult,
    leads: list[LeadRecord],
    priors: dict[str, HybridMatchContext],
    callbacks: PipelineCallbacks,
    client: Any | None = None,
    batch_size: int = SLAYER_MICRO_BATCH_SIZE,
) -> dict[str, SlayerVerdict]:
    await callbacks.on_phase(PipelinePhase.SLAYING)
    batches = [leads[i : i + batch_size] for i in range(0, len(leads), max(1, batch_size))]
    await callbacks.on_log(
        f"[SlayerSwarm] Unleashing {startup.slaying_level.value} Slayer ({settings.gemini_workhorse_model}) across {len(leads)} leads in {len(batches)} micro-batches..."
    )

    system_prompt = (
        build_slayer_system_prompt(startup.slaying_level, audit.anti_icp_red_flags)
        + "\n\nEvaluate EVERY lead in the batch independently and return one verdict per `lead_id` in `verdicts`."
    )

    genai_client = client or genai.Client(
        api_key=key_rotator.next_key(),
        http_options=genai.types.HttpOptions(
            retry_options=genai.types.HttpRetryOptions(attempts=1)
        ),
    )

    async def _evaluate_batch(batch: list[LeadRecord]) -> list[SlayerVerdict]:
        leads_block = "\n\n".join(
            _format_lead_for_slayer(lead, priors[lead.id]) for lead in batch
        )
        prompt = (
            f"PRODUCT: {startup.product_name} — {audit.sharpened_value_prop}\n"
            f"PRODUCT DESCRIPTION: {startup.description}\n\n"
            f"INTERROGATE THESE {len(batch)} LEADS AGAINST PRODUCT & MATCHED ICP:\n\n{leads_block}"
        )

        t0 = time.perf_counter()
        response = await genai_client.aio.models.generate_content(
            model=settings.gemini_workhorse_model,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=SlayerBatchLLMResponse,
            ),
        )
        per_lead_ms = max(1, int(((time.perf_counter() - t0) * 1000) / len(batch)))
        parsed = SlayerBatchLLMResponse.model_validate_json(response.text or "{}")

        by_id = {v.lead_id: v for v in parsed.verdicts}
        results: list[SlayerVerdict] = []
        for lead in batch:
            item = by_id.get(lead.id)
            if item is None:
                item = SlayerBatchItem(
                    lead_id=lead.id,
                    disqualifier_signals_found=["Incomplete model batch item"],
                    tier_triggered="TIER_3_FRICTION",
                    rejection_category=RejectionCategory.NO_URGENCY_SIGNAL,
                    reasoning="Insufficient urgency signal verified during batch triage.",
                    survived=False,
                    headline_tag="KILLED: Weak Signal",
                    confidence=0.75,
                )
            results.append(
                _to_slayer_verdict(item, priors[lead.id], startup, per_lead_ms)
            )
        return results

    executor = GentleAdaptiveExecutor(
        concurrency=3,
        launch_stagger_s=0.12,
        max_retries=2,
        backoff_schedule=(2.0, 5.0),
    )
    verdicts: dict[str, SlayerVerdict] = {}
    async for _, batch_verdicts in executor.run_stream(batches, _evaluate_batch):
        await callbacks.on_model_call(ModelId.GEMINI_3_5_FLASH_LITE)
        for verdict in batch_verdicts:
            verdicts[verdict.lead_id] = verdict
            await callbacks.on_verdict(verdict)

    killed_n = sum(1 for v in verdicts.values() if not v.survived)
    surv_n = len(verdicts) - killed_n
    await callbacks.on_log(
        f"[SlayerSwarm] Bloodbath complete: {killed_n} KILLED, {surv_n} SURVIVED."
    )
    return verdicts


class SlayerSwarmADKAgent(BaseAgent):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    callbacks: Any

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncIterator[Event]:
        startup = StartupInput.model_validate(ctx.session.state["startup_input"])
        audit = MarketAuditResult.model_validate(ctx.session.state["market_audit"])
        leads = [LeadRecord.model_validate(item) for item in ctx.session.state["leads"]]
        priors = {
            lid: HybridMatchContext.model_validate(raw)
            for lid, raw in ctx.session.state["hybrid_priors"].items()
        }
        verdicts = await execute_slayer_swarm(
            startup, audit, leads, priors, self.callbacks
        )
        verdicts_dict = {
            lid: v.model_dump(mode="json") for lid, v in verdicts.items()
        }
        ctx.session.state["verdicts"] = verdicts_dict
        killed = sum(1 for v in verdicts.values() if not v.survived)
        yield Event(
            author=self.name,
            content=genai.types.Content(
                role="model",
                parts=[
                    genai.types.Part.from_text(
                        text=f"Slayer processed {len(verdicts)} leads ({killed} killed)"
                    )
                ],
            ),
            actions=EventActions(state_delta={"verdicts": verdicts_dict}),
        )
