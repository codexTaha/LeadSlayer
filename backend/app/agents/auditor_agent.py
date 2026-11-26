import asyncio
from typing import Any
from google import genai
from google.genai import types
from google.adk.agents import BaseAgent
from google.adk.events import Event, EventActions
from google.adk.agents.invocation_context import InvocationContext

from app.agents.interface import PipelineCallbacks
from app.agents.prompts import AUDITOR_SYSTEM_PROMPT
from app.config import settings
from app.memory.exceptions import GeminiAPIUnavailableError, is_transient_api_error
from app.models.schemas import MarketAuditResult, ModelId, PipelinePhase, StartupInput


async def run_market_auditor(
    startup_input: StartupInput,
    callbacks: PipelineCallbacks | None = None,
    client: genai.Client | None = None,
    model_id: str = "gemini-4-hydrogen",
) -> MarketAuditResult:
    """
    Executes Market Auditor using gemini-4-hydrogen to audit founder assumptions
    and produce MarketAuditResult with anti-ICP red flags.
    """
    if callbacks:
        await callbacks.on_phase(PipelinePhase.AUDITING)
        await callbacks.on_model_call(ModelId.GEMINI_4_HYDROGEN)
        await callbacks.on_log(f"Auditing market reality for '{startup_input.product_name}'...")

    cli = client or genai.Client(api_key=settings.gemini_api_key)

    prompt = (
        f"Startup Product: {startup_input.product_name}\n"
        f"Product URL: {startup_input.product_url or 'N/A'}\n"
        f"Description:\n{startup_input.description}\n\n"
        f"Founder Assumptions:\n{startup_input.founder_assumptions}\n"
    )

    config = types.GenerateContentConfig(
        system_instruction=AUDITOR_SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=MarketAuditResult,
        temperature=0.2,
    )

    attempts = 0
    max_retries = 3
    response = None

    while attempts <= max_retries:
        try:
            response = await cli.aio.models.generate_content(
                model=model_id,
                contents=[prompt],
                config=config,
            )
            break
        except Exception as exc:
            is_trans, status = is_transient_api_error(exc)
            if is_trans and attempts < max_retries:
                attempts += 1
                if callbacks:
                    await callbacks.on_log(f"Model {model_id} high demand ({status or 503}). Retrying in {attempts * 2.5}s...")
                await asyncio.sleep(attempts * 2.5)
                continue
            else:
                if isinstance(exc, GeminiAPIUnavailableError):
                    raise
                raise GeminiAPIUnavailableError(
                    user_message="Gemini API limit reached or service is temporarily overloaded during Market Audit. Please wait a short while and try again.",
                    status_code=status or 503,
                    raw_error=str(exc),
                )

    if not response or not response.text:
        raise GeminiAPIUnavailableError(
            user_message="Gemini Market Auditor returned an empty response.",
            raw_error="No text in generate_content response",
        )
    audit_result = MarketAuditResult.model_validate_json(response.text)

    if callbacks:
        await callbacks.on_audit(audit_result)
        await callbacks.on_log(
            f"Market Audit complete. Readiness Score: {audit_result.market_readiness_score}/100. "
            f"Generated {len(audit_result.anti_icp_red_flags)} Anti-ICP Red Flags."
        )

    return audit_result


class AuditorAgent(BaseAgent):
    """Google ADK BaseAgent wrapper for Market Auditor."""

    callbacks: Any = None
    client: Any = None
    model_id: str = "gemini-4-hydrogen"

    async def _run_async_impl(self, ctx: InvocationContext):
        startup_input_data = ctx.session.state.get("startup_input")
        if not startup_input_data:
            raise ValueError("No startup_input found in session state for AuditorAgent")

        startup_input = (
            startup_input_data
            if isinstance(startup_input_data, StartupInput)
            else StartupInput.model_validate(startup_input_data)
        )

        audit = await run_market_auditor(
            startup_input=startup_input,
            callbacks=self.callbacks,
            client=self.client,
            model_id=self.model_id,
        )

        ctx.session.state["market_audit"] = audit.model_dump()
        yield Event(
            author=self.name,
            actions=EventActions(state_delta={"market_audit": audit.model_dump()}),
        )
