from typing import Any
from google import genai
from google.genai import types
from google.adk.agents import BaseAgent
from google.adk.events import Event, EventActions
from google.adk.agents.invocation_context import InvocationContext

from app.agents.interface import PipelineCallbacks
from app.agents.rate_limiter import GentleAdaptiveExecutor
from app.agents.structured_outputs import _EnrichedLeadPatch
from app.config import settings
from app.memory.exceptions import GeminiAPIUnavailableError, is_transient_api_error
from app.memory.vector_store import HybridMatchContext, HybridMemoryStore
from app.models.schemas import HunterReport, LeadRecord, ModelId, PipelinePhase


async def run_hunter_swarm(
    leads: list[LeadRecord],
    memory_store: HybridMemoryStore,
    callbacks: PipelineCallbacks | None = None,
    client: genai.Client | None = None,
    workhorse_model_id: str = "gemini-3.5-flash-lite",
) -> tuple[list[LeadRecord], dict[str, HybridMatchContext], HunterReport]:
    """
    Ingests and validates leads. If > 20% are missing tech_stack or recent_signal,
    enriches them in batches via gemini-3.5-flash-lite. Then embeds and computes
    Dual-Polarity hybrid retrieval priors for all leads.
    """
    if callbacks:
        await callbacks.on_phase(PipelinePhase.HUNTING)
        await callbacks.on_log(f"Hunter Swarm ingesting {len(leads)} raw B2B leads...")

    cli = client or genai.Client(api_key=settings.gemini_api_key)

    # Check for sparsity
    sparse_leads = [
        lead for lead in leads
        if (not lead.tech_stack or not lead.recent_signal)
    ]
    sparsity_ratio = len(sparse_leads) / max(1, len(leads))

    enriched_count = 0
    if sparsity_ratio > 0.20:
        if callbacks:
            await callbacks.on_log(
                f"Detected sparse CSV ({len(sparse_leads)}/{len(leads)} sparse leads). "
                f"Enriching via {workhorse_model_id}..."
            )

        executor = GentleAdaptiveExecutor(concurrency=3, launch_stagger_s=0.1)

        async def _enrich_worker(lead: LeadRecord) -> _EnrichedLeadPatch:
            prompt = (
                f"Infer tech stack and recent operational signals for B2B lead:\n"
                f"Role: {lead.role}\nCompany: {lead.company}\nIndustry: {lead.industry}\n"
                f"Bio: {lead.bio_snippet}\n"
            )
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_EnrichedLeadPatch,
                temperature=0.2,
            )
            resp = await cli.aio.models.generate_content(
                model=workhorse_model_id,
                contents=[prompt],
                config=config,
            )
            if callbacks:
                await callbacks.on_model_call(ModelId.GEMINI_3_5_FLASH_LITE)
            patch = _EnrichedLeadPatch.model_validate_json(resp.text or "{}")
            patch.lead_id = lead.id
            return patch

        async for lead, patch in executor.run_stream(sparse_leads, _enrich_worker):
            if not lead.tech_stack and patch.inferred_tech_stack:
                lead.tech_stack = patch.inferred_tech_stack
            if not lead.recent_signal and patch.inferred_signal:
                lead.recent_signal = patch.inferred_signal
            enriched_count += 1
    else:
        if callbacks:
            await callbacks.on_log("Lead list validated. Clean data detected, skipping enrichment LLM calls.")

    # Embed and compute Dual-Polarity priors via NumPy dot products
    priors, emb_calls = await memory_store.index_and_score_leads(leads)
    if callbacks:
        for _ in range(emb_calls):
            await callbacks.on_model_call(ModelId.GEMINI_EMBEDDING_2)
        await callbacks.on_log(f"Dual-Polarity hybrid vectors calculated for all {len(leads)} leads.")

    report = HunterReport(
        hunt_queries=[],
        enriched_sparse_leads=enriched_count,
        url_fetches_succeeded=0,
        total_leads_ready=len(leads),
    )

    if callbacks and hasattr(callbacks, "on_hunter_report"):
        await callbacks.on_hunter_report(report)

    return leads, priors, report


class HunterSwarmAgent(BaseAgent):
    """Google ADK BaseAgent wrapper for Hunter Swarm."""

    callbacks: Any = None
    client: Any = None
    memory_store: Any = None
    workhorse_model_id: str = "gemini-3.5-flash-lite"

    async def _run_async_impl(self, ctx: InvocationContext):
        leads_data = ctx.session.state.get("leads", [])
        leads = [
            l if isinstance(l, LeadRecord) else LeadRecord.model_validate(l)
            for l in leads_data
        ]

        leads, priors, report = await run_hunter_swarm(
            leads=leads,
            memory_store=self.memory_store,
            callbacks=self.callbacks,
            client=self.client,
            workhorse_model_id=self.workhorse_model_id,
        )

        ctx.session.state["leads"] = [l.model_dump() for l in leads]
        ctx.session.state["priors"] = {k: v.model_dump() for k, v in priors.items()}
        ctx.session.state["hunter_report"] = report.model_dump()

        yield Event(
            author=self.name,
            actions=EventActions(
                state_delta={
                    "leads": [l.model_dump() for l in leads],
                    "priors": {k: v.model_dump() for k, v in priors.items()},
                    "hunter_report": report.model_dump(),
                }
            ),
        )
