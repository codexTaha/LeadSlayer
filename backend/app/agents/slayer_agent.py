import time
from typing import Any
from google import genai
from google.genai import types
from google.adk.agents import BaseAgent
from google.adk.events import Event, EventActions
from google.adk.agents.invocation_context import InvocationContext

from app.agents.interface import PipelineCallbacks
from app.agents.prompts import build_slayer_system_prompt
from app.agents.rate_limiter import GentleAdaptiveExecutor
from app.agents.structured_outputs import _SlayerLLMResponse
from app.config import settings
from app.memory.exceptions import GeminiAPIUnavailableError, is_transient_api_error
from app.memory.vector_store import HybridMatchContext
from app.models.schemas import (
    LeadRecord,
    ModelId,
    PipelinePhase,
    RejectionCategory,
    SlayerVerdict,
    SlayingLevel,
)


def normalize_headline(headline: str, survived: bool) -> str:
    words = headline.strip().split()
    prefix = "SURVIVED:" if survived else "KILLED:"
    
    if words and words[0].upper() == prefix:
        clean_words = words[:5]
        return " ".join(clean_words)
    
    # Remove any stray prefix
    if words and (words[0].upper().startswith("KILLED") or words[0].upper().startswith("SURVIVED")):
        words = words[1:]
    
    combined = [prefix] + words[:4]
    return " ".join(combined)


async def run_slayer_triage(
    leads: list[LeadRecord],
    priors: dict[str, HybridMatchContext],
    slaying_level: SlayingLevel,
    anti_icp_red_flags: list[str],
    callbacks: PipelineCallbacks | None = None,
    client: genai.Client | None = None,
    workhorse_model_id: str = "gemini-3.5-flash-lite",
) -> dict[str, SlayerVerdict]:
    """
    Executes adversarial Slayer Agent on all leads using gemini-3.5-flash-lite
    orchestrated through GentleAdaptiveExecutor.
    """
    if callbacks:
        await callbacks.on_phase(PipelinePhase.SLAYING)
        await callbacks.on_log(
            f"Slayer Agent engaging {len(leads)} leads with {slaying_level.value} aggression..."
        )

    cli = client or genai.Client(api_key=settings.gemini_api_key)
    system_prompt = build_slayer_system_prompt(slaying_level, anti_icp_red_flags)

    executor = GentleAdaptiveExecutor(
        concurrency=settings.slayer_concurrency,
        launch_stagger_s=0.06,
        max_retries=3,
    )

    verdicts: dict[str, SlayerVerdict] = {}

    async def _slayer_worker(lead: LeadRecord) -> tuple[LeadRecord, _SlayerLLMResponse, int]:
        start_t = time.time()
        prior_ctx = priors.get(lead.id)

        prompt = (
            f"EVALUATE THIS LEAD:\n"
            f"Lead ID: {lead.id}\n"
            f"Name: {lead.full_name}\n"
            f"Role: {lead.role}\n"
            f"Company: {lead.company} ({lead.domain})\n"
            f"Industry: {lead.industry}\n"
            f"Headcount: {lead.employee_count}\n"
            f"Funding Stage: {lead.funding_stage}\n"
            f"Tech Stack: {', '.join(lead.tech_stack) if lead.tech_stack else 'None stated'}\n"
            f"Recent Signal: {lead.recent_signal or 'None stated'}\n"
            f"Bio Snippet: {lead.bio_snippet}\n"
        )
        if prior_ctx:
            prompt += (
                f"\nVector Engine Match:\n"
                f"- Matched ICP: {prior_ctx.best_icp.name}\n"
                f"- ICP Similarity Score: {prior_ctx.icp_similarity_score:.2f}\n"
                f"- Anti-ICP Similarity Score: {prior_ctx.anti_icp_similarity_score:.2f} ({prior_ctx.matched_anti_icp_rule})\n"
                f"- Structural Match Score: {prior_ctx.structural_match_score:.2f}\n"
                f"- Stage 2 Prior Score: {prior_ctx.prior_score_100}/100\n"
            )

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=_SlayerLLMResponse,
            temperature=0.1,
        )

        resp = await cli.aio.models.generate_content(
            model=workhorse_model_id,
            contents=[prompt],
            config=config,
        )
        latency_ms = int((time.time() - start_t) * 1000)

        if not resp.text:
            raise GeminiAPIUnavailableError(
                user_message=f"Gemini Slayer returned empty response for lead {lead.id}.",
                raw_error="No text in generate_content response",
            )

        llm_response = _SlayerLLMResponse.model_validate_json(resp.text)
        return lead, llm_response, latency_ms

    async for lead, (lead_rec, llm_resp, latency_ms) in executor.run_stream(leads, _slayer_worker):
        prior_ctx = priors.get(lead.id)
        prior_score = prior_ctx.prior_score_100 if prior_ctx else 50
        conf = llm_resp.confidence

        # Qualification score fusion formula
        if llm_resp.survived:
            qualification_score = max(65, min(99, round(0.40 * prior_score + 0.60 * (conf * 100))))
            rejection_cat = None
        else:
            qualification_score = max(4, min(62, round(0.40 * prior_score + 0.60 * ((1 - conf) * 100))))
            rejection_cat = llm_resp.rejection_category or RejectionCategory.NO_URGENCY_SIGNAL

        headline = normalize_headline(llm_resp.headline_tag, llm_resp.survived)

        verdict = SlayerVerdict(
            lead_id=lead.id,
            survived=llm_resp.survived,
            resurrected_by_user=False,
            rejection_category=rejection_cat,
            headline_tag=headline,
            reasoning=llm_resp.reasoning,
            matched_icp_id=prior_ctx.best_icp.id if prior_ctx else None,
            icp_similarity_score=prior_ctx.icp_similarity_score if prior_ctx else 0.5,
            anti_icp_similarity_score=prior_ctx.anti_icp_similarity_score if prior_ctx else 0.0,
            structural_match_score=prior_ctx.structural_match_score if prior_ctx else 0.5,
            qualification_score=qualification_score,
            confidence=round(conf, 2),
            slaying_level_applied=slaying_level,
            latency_ms=latency_ms,
            model_used=ModelId.GEMINI_3_5_FLASH_LITE,
        )

        verdicts[lead.id] = verdict

        if callbacks:
            await callbacks.on_model_call(ModelId.GEMINI_3_5_FLASH_LITE)
            await callbacks.on_verdict(verdict)

    if callbacks:
        survived_count = sum(1 for v in verdicts.values() if v.survived)
        killed_count = len(verdicts) - survived_count
        kill_pct = (killed_count / max(1, len(verdicts))) * 100
        await callbacks.on_log(
            f"Slaying complete: {killed_count}/{len(verdicts)} leads KILLED ({kill_pct:.1f}%), "
            f"{survived_count} survived."
        )

    return verdicts


class SlayerSwarmAgent(BaseAgent):
    """Google ADK BaseAgent wrapper for Slayer Swarm."""

    callbacks: Any = None
    client: Any = None
    workhorse_model_id: str = "gemini-3.5-flash-lite"

    async def _run_async_impl(self, ctx: InvocationContext):
        leads_data = ctx.session.state.get("leads", [])
        leads = [
            l if isinstance(l, LeadRecord) else LeadRecord.model_validate(l)
            for l in leads_data
        ]
        priors_raw = ctx.session.state.get("priors", {})
        priors = {
            k: v if isinstance(v, HybridMatchContext) else HybridMatchContext.model_validate(v)
            for k, v in priors_raw.items()
        }

        startup_data = ctx.session.state.get("startup_input", {})
        startup_input = (
            startup_data
            if isinstance(startup_data, StartupInput)
            else StartupInput.model_validate(startup_data)
        )

        audit_data = ctx.session.state.get("market_audit", {})
        audit = (
            audit_data
            if isinstance(audit_data, MarketAuditResult)
            else MarketAuditResult.model_validate(audit_data)
        )

        verdicts = await run_slayer_triage(
            leads=leads,
            priors=priors,
            slaying_level=startup_input.slaying_level,
            anti_icp_red_flags=audit.anti_icp_red_flags,
            callbacks=self.callbacks,
            client=self.client,
            workhorse_model_id=self.workhorse_model_id,
        )

        ctx.session.state["verdicts"] = {k: v.model_dump() for k, v in verdicts.items()}
        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={"verdicts": {k: v.model_dump() for k, v in verdicts.items()}}
            ),
        )
