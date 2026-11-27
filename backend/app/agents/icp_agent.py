from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from google import genai
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from pydantic import ConfigDict

from app.agents.interface import PipelineCallbacks
from app.agents.key_rotator import key_rotator
from app.agents.prompts import ICP_ENGINE_SYSTEM_PROMPT
from app.agents.rate_limiter import GentleAdaptiveExecutor
from app.agents.structured_outputs import ICPBatchOutput
from app.config import settings
from app.memory.registry import memory_registry
from app.models.schemas import ICPProfile, MarketAuditResult, ModelId, PipelinePhase, StartupInput


async def execute_icp_engine(
    run_id: str,
    startup: StartupInput,
    audit: MarketAuditResult,
    callbacks: PipelineCallbacks,
    client: Any | None = None,
) -> list[ICPProfile]:
    await callbacks.on_phase(PipelinePhase.ICP_GENERATION)
    await callbacks.on_log(
        f"[ICPEngine] Generating 3 ICPs ({settings.gemini_brain_model}) and indexing vectors ({settings.gemini_embedding_model})..."
    )

    prompt = (
        f"Product: {startup.product_name}\n"
        f"Sharpened Value Prop: {audit.sharpened_value_prop}\n"
        f"Market Reality: {audit.market_reality_summary}\n"
        f"Anti-ICP Red Flags: {'; '.join(audit.anti_icp_red_flags)}\n"
        f"Description: {startup.description}\n\n"
        "Generate exactly 3 distinct Ideal Customer Profiles (icp_1, icp_2, icp_3)."
    )

    genai_client = client or genai.Client(
        api_key=key_rotator.next_key(),
        http_options=genai.types.HttpOptions(
            retry_options=genai.types.HttpRetryOptions(attempts=1)
        ),
    )

    async def _call_icp(_: int) -> list[ICPProfile]:
        resp = await genai_client.aio.models.generate_content(
            model=settings.gemini_brain_model,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=ICP_ENGINE_SYSTEM_PROMPT,
                temperature=0.2,
                response_mime_type="application/json",
                response_schema=ICPBatchOutput,
            ),
        )
        if not resp.text:
            raise RuntimeError("ICPEngine returned empty output.")
        parsed = ICPBatchOutput.model_validate_json(resp.text)
        normalized: list[ICPProfile] = []
        for idx, icp in enumerate(parsed.icps[:3], start=1):
            icp_id = f"icp_{idx}"
            normalized.append(
                icp.model_copy(update={"id": icp_id, "vector_doc_id": icp_id})
            )
        return normalized

    executor = GentleAdaptiveExecutor(
        concurrency=1, launch_stagger_s=0.0, max_retries=2, backoff_schedule=(2.0, 5.0)
    )
    icps: list[ICPProfile] = []
    async for _, res in executor.run_stream([0], _call_icp):
        icps = res

    await callbacks.on_model_call(ModelId.GEMINI_4_HYDROGEN)
    await callbacks.on_icps(icps)

    memory_store = memory_registry.get_or_create(run_id)
    emb_calls = await memory_store.index_knowledge(startup, audit, icps)
    for _ in range(emb_calls):
        await callbacks.on_model_call(ModelId.GEMINI_EMBEDDING_2)

    await callbacks.on_log(
        f"[ICPEngine] Embedded {len(icps)} ICPs & product chunks ({emb_calls} live embedding batch calls)."
    )
    return icps


class ICPEngineADKAgent(BaseAgent):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    run_id: str
    callbacks: Any

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncIterator[Event]:
        startup = StartupInput.model_validate(ctx.session.state["startup_input"])
        audit = MarketAuditResult.model_validate(ctx.session.state["market_audit"])
        icps = await execute_icp_engine(self.run_id, startup, audit, self.callbacks)
        icps_list = [icp.model_dump(mode="json") for icp in icps]
        ctx.session.state["icps"] = icps_list
        yield Event(
            author=self.name,
            content=genai.types.Content(
                role="model",
                parts=[genai.types.Part.from_text(text=f"Indexed {len(icps)} ICPs")],
            ),
            actions=EventActions(state_delta={"icps": icps_list}),
        )
