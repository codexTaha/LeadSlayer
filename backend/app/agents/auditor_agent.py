from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from google import genai
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from pydantic import ConfigDict

from app.agents.interface import PipelineCallbacks
from app.agents.prompts import AUDITOR_SYSTEM_PROMPT
from app.agents.rate_limiter import GentleAdaptiveExecutor
from app.config import settings
from app.models.schemas import MarketAuditResult, ModelId, PipelinePhase, StartupInput
from app.services.url_fetcher import fetch_site_context


async def _run_optional_search_grounding(startup: StartupInput) -> str | None:
    """
    Lightweight optional Gemini Search Grounding pass for real competitor & market context.
    Never fails the pipeline or spams logs if search grounding is unavailable or throttled.
    """
    if not settings.gemini_api_key:
        return None
    try:
        client = genai.Client(
            api_key=key_rotator.next_key(),
            http_options=genai.types.HttpOptions(
                retry_options=genai.types.HttpRetryOptions(attempts=1)
            ),
        )
        res = await client.aio.models.generate_content(
            model=settings.gemini_workhorse_model,
            contents=(
                f"Briefly list 3 real competing products and common buyer switching triggers "
                f"for this category in 4 concise bullets.\nProduct: {startup.product_name}\n"
                f"Description: {startup.description}"
            ),
            config=genai.types.GenerateContentConfig(
                tools=[genai.types.Tool(google_search=genai.types.GoogleSearch())],
                temperature=0.2,
            ),
        )
        text = (res.text or "").strip()
        return text if text else None
    except Exception:
        return None


async def execute_market_audit(
    startup: StartupInput,
    callbacks: PipelineCallbacks,
    client: Any | None = None,
) -> MarketAuditResult:
    await callbacks.on_phase(PipelinePhase.AUDITING)
    await callbacks.on_log(
        f"[MarketAuditor] Auditing '{startup.product_name}' on {settings.gemini_brain_model}..."
    )

    site_context = await fetch_site_context(startup.product_url, timeout_s=3.0)
    if site_context:
        await callbacks.on_log(
            f"[MarketAuditor] Extracted live website context from {startup.product_url}."
        )

    search_notes = await _run_optional_search_grounding(startup)
    if search_notes:
        await callbacks.on_log(
            "[MarketAuditor] Enriched market audit with Google Search grounding."
        )

    prompt_parts = [
        f"Product Name: {startup.product_name}",
        f"Product URL: {startup.product_url or 'N/A'}",
        f"Product Description:\n{startup.description}",
        f"Founder's Market Assumptions:\n{startup.founder_assumptions}",
    ]
    if site_context:
        prompt_parts.append(f"Live Website Content:\n{site_context}")
    if search_notes:
        prompt_parts.append(f"Live Search Market Intel:\n{search_notes}")

    user_prompt = "\n\n".join(prompt_parts)
    genai_client = client or genai.Client(
        api_key=key_rotator.next_key(),
        http_options=genai.types.HttpOptions(
            retry_options=genai.types.HttpRetryOptions(attempts=1)
        ),
    )

    async def _call_auditor(_: int) -> MarketAuditResult:
        resp = await genai_client.aio.models.generate_content(
            model=settings.gemini_brain_model,
            contents=user_prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=AUDITOR_SYSTEM_PROMPT,
                temperature=0.2,
                response_mime_type="application/json",
                response_schema=MarketAuditResult,
            ),
        )
        if not resp.text:
            raise RuntimeError("MarketAuditor returned empty output.")
        audit = MarketAuditResult.model_validate_json(resp.text)
        return audit.model_copy(
            update={
                "url_scraped_context_used": bool(site_context),
                "search_grounding_used": bool(search_notes),
            }
        )

    executor = GentleAdaptiveExecutor(
        concurrency=1, launch_stagger_s=0.0, max_retries=2, backoff_schedule=(2.0, 5.0)
    )
    audit_result: MarketAuditResult | None = None
    async for _, res in executor.run_stream([0], _call_auditor):
        audit_result = res

    assert audit_result is not None
    await callbacks.on_model_call(ModelId.GEMINI_4_HYDROGEN)
    await callbacks.on_audit(audit_result)
    await callbacks.on_log(
        f"[MarketAuditor] Readiness {audit_result.market_readiness_score}/100 · Locked {len(audit_result.anti_icp_red_flags)} Anti-ICP kill rules."
    )
    return audit_result


class MarketAuditorADKAgent(BaseAgent):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    callbacks: Any

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncIterator[Event]:
        startup = StartupInput.model_validate(ctx.session.state["startup_input"])
        audit = await execute_market_audit(startup, self.callbacks)
        audit_dict = audit.model_dump(mode="json")
        ctx.session.state["market_audit"] = audit_dict
        yield Event(
            author=self.name,
            content=genai.types.Content(
                role="model",
                parts=[genai.types.Part.from_text(text=audit.sharpened_value_prop)],
            ),
            actions=EventActions(state_delta={"market_audit": audit_dict}),
        )
