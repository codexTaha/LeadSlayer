import asyncio
from typing import Any
from google import genai
from google.genai import types
from google.adk.agents import BaseAgent
from google.adk.events import Event, EventActions
from google.adk.agents.invocation_context import InvocationContext

from app.agents.interface import PipelineCallbacks
from app.agents.prompts import ICP_ENGINE_SYSTEM_PROMPT
from app.agents.structured_outputs import _ICPBatchOutput
from app.config import settings
from app.memory.exceptions import GeminiAPIUnavailableError, is_transient_api_error
from app.memory.vector_store import HybridMemoryStore
from app.models.schemas import ICPProfile, MarketAuditResult, ModelId, PipelinePhase, StartupInput


async def run_icp_engine(
    startup_input: StartupInput,
    audit: MarketAuditResult,
    memory_store: HybridMemoryStore,
    callbacks: PipelineCallbacks | None = None,
    client: genai.Client | None = None,
    model_id: str = "gemini-4-hydrogen",
) -> list[ICPProfile]:
    """
    Executes ICP Engine using gemini-4-hydrogen to generate 3 diverse Ideal Customer Profiles,
    then indexes product truth, ICPs, and anti-ICPs into vector memory.
    """
    if callbacks:
        await callbacks.on_phase(PipelinePhase.ICP_GENERATION)
        await callbacks.on_model_call(ModelId.GEMINI_4_HYDROGEN)
        await callbacks.on_log("Generating 3 targeted ICP profiles and building vector memory...")

    cli = client or genai.Client(api_key=settings.gemini_api_key)

    prompt = (
        f"Startup Product: {startup_input.product_name}\n"
        f"Sharpened Value Prop: {audit.sharpened_value_prop}\n"
        f"Market Reality: {audit.market_reality_summary}\n\n"
        f"Founder Blind Spots Identified:\n- " + "\n- ".join(audit.founder_blind_spots) + "\n\n"
        f"Anti-ICP Red Flags to Avoid:\n- " + "\n- ".join(audit.anti_icp_red_flags) + "\n"
    )

    config = types.GenerateContentConfig(
        system_instruction=ICP_ENGINE_SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=_ICPBatchOutput,
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
                    user_message="Gemini API limit reached or service is temporarily overloaded during ICP generation. Please wait a short while and try again.",
                    status_code=status or 503,
                    raw_error=str(exc),
                )

    if not response or not response.text:
        raise GeminiAPIUnavailableError(
            user_message="Gemini ICP Engine returned an empty response.",
            raw_error="No text in generate_content response",
        )
    batch_out = _ICPBatchOutput.model_validate_json(response.text)
    icps = batch_out.icps

    # Ensure correct IDs
    for idx, icp in enumerate(icps, start=1):
        if not icp.id:
            icp.id = f"icp_{idx}"
        if not icp.vector_doc_id:
            icp.vector_doc_id = f"icp_{idx}"

    if callbacks:
        await callbacks.on_icps(icps)
        for icp in icps:
            await callbacks.on_log(f"Generated ICP [{icp.id}]: {icp.name} ({', '.join(icp.target_roles)})")

    # Index knowledge into memory store
    emb_calls = await memory_store.index_knowledge(startup_input, audit, icps)
    if callbacks:
        for _ in range(emb_calls):
            await callbacks.on_model_call(ModelId.GEMINI_EMBEDDING_2)
        await callbacks.on_log(f"Vector memory indexed with {len(memory_store.product_chunks)} product chunks and {len(icps)} ICPs.")

    return icps


class ICPAgent(BaseAgent):
    """Google ADK BaseAgent wrapper for ICP Engine."""

    callbacks: Any = None
    client: Any = None
    memory_store: Any = None
    model_id: str = "gemini-4-hydrogen"

    async def _run_async_impl(self, ctx: InvocationContext):
        startup_data = ctx.session.state.get("startup_input")
        audit_data = ctx.session.state.get("market_audit")

        startup_input = (
            startup_data
            if isinstance(startup_data, StartupInput)
            else StartupInput.model_validate(startup_data)
        )
        audit = (
            audit_data
            if isinstance(audit_data, MarketAuditResult)
            else MarketAuditResult.model_validate(audit_data)
        )

        icps = await run_icp_engine(
            startup_input=startup_input,
            audit=audit,
            memory_store=self.memory_store,
            callbacks=self.callbacks,
            client=self.client,
            model_id=self.model_id,
        )

        icps_serialized = [icp.model_dump() for icp in icps]
        ctx.session.state["icps"] = icps_serialized
        yield Event(
            author=self.name,
            actions=EventActions(state_delta={"icps": icps_serialized}),
        )
