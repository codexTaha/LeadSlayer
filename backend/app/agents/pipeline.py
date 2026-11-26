from typing import Any
from google import genai
from google.adk.agents import SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agents.auditor_agent import AuditorAgent, run_market_auditor
from app.agents.hunter_agent import HunterSwarmAgent, run_hunter_swarm
from app.agents.icp_agent import ICPAgent, run_icp_engine
from app.agents.interface import PipelineCallbacks, PipelineFinalResult
from app.agents.slayer_agent import SlayerSwarmAgent, run_slayer_triage
from app.agents.sniper_agent import SniperAgent, run_sniper_drafting
from app.config import settings
from app.memory.exceptions import GeminiAPIUnavailableError
from app.memory.registry import memory_registry
from app.memory.vector_store import HybridMemoryStore
from app.models.schemas import (
    EmailDraft,
    HunterReport,
    ICPProfile,
    LeadRecord,
    MarketAuditResult,
    PipelinePhase,
    SlayerVerdict,
    StartupInput,
)


async def run_live_pipeline(
    run_id: str,
    startup_input: StartupInput,
    leads: list[LeadRecord],
    callbacks: PipelineCallbacks,
    client: genai.Client | None = None,
) -> PipelineFinalResult:
    """
    Master entry point for LeadSlayer AI Stages 2 & 3.
    Executes the 5-stage agent sequence:
    1. Market Auditor (gemini-4-hydrogen) -> anti-ICP red flags
    2. ICP Engine (gemini-4-hydrogen) -> 3 ICPs + vector memory build
    3. Hunter Swarm (fast validation / gemini-3.5-flash-lite) -> dual-polarity hybrid retrieval
    4. Slayer Swarm (gemini-3.5-flash-lite) -> adversarial triage (~80% killed)
    5. Sniper Agent (gemini-4-hydrogen) -> grounded precision cold emails

    Propagates GeminiAPIUnavailableError honestly if quotas/service fail.
    """
    api_key = settings.gemini_api_key or ""
    if not api_key and client is None:
        raise GeminiAPIUnavailableError(
            user_message="GEMINI_API_KEY is not configured. Please add your GEMINI_API_KEY to .env.",
            status_code=401,
            raw_error="No API key was provided",
        )
    cli = client or genai.Client(api_key=api_key)
    memory_store = memory_registry.get_or_create(run_id)

    # 1. Step 1: Market Auditor
    audit = await run_market_auditor(
        startup_input=startup_input,
        callbacks=callbacks,
        client=cli,
        model_id=settings.gemini_brain_model,
    )

    # 2. Step 2: ICP Engine + Stage 2 Vector Indexing
    icps = await run_icp_engine(
        startup_input=startup_input,
        audit=audit,
        memory_store=memory_store,
        callbacks=callbacks,
        client=cli,
        model_id=settings.gemini_brain_model,
    )

    # 3. Step 3: Hunter Swarm + Dual-Polarity Hybrid Priors
    leads, priors, report = await run_hunter_swarm(
        leads=leads,
        memory_store=memory_store,
        callbacks=callbacks,
        client=cli,
        workhorse_model_id=settings.gemini_workhorse_model,
    )

    # 4. Step 4: Slayer Swarm (Adversarial Triage)
    verdicts = await run_slayer_triage(
        leads=leads,
        priors=priors,
        slaying_level=startup_input.slaying_level,
        anti_icp_red_flags=audit.anti_icp_red_flags,
        callbacks=callbacks,
        client=cli,
        workhorse_model_id=settings.gemini_workhorse_model,
    )

    # 5. Step 5: Sniper Agent (Surviving Lead Precision Emails)
    icps_map = {icp.id: icp for icp in icps}
    surviving_leads = [lead for lead in leads if verdicts.get(lead.id) and verdicts[lead.id].survived]

    emails = await run_sniper_drafting(
        surviving_leads=surviving_leads,
        verdicts=verdicts,
        icps_map=icps_map,
        memory_store=memory_store,
        callbacks=callbacks,
        client=cli,
        brain_model_id=settings.gemini_brain_model,
    )

    if callbacks:
        await callbacks.on_phase(PipelinePhase.READY)
        await callbacks.on_log(
            f"Pipeline completed successfully. {len(verdicts)} leads triaged, "
            f"{len(emails)} precision emails drafted."
        )

    return PipelineFinalResult(
        run_id=run_id,
        market_audit=audit,
        icps=icps,
        hunter_report=report,
        verdicts=verdicts,
        emails=emails,
    )


def build_adk_pipeline(
    memory_store: HybridMemoryStore,
    callbacks: PipelineCallbacks | None = None,
    client: genai.Client | None = None,
) -> SequentialAgent:
    """Builds the ADK SequentialAgent pipeline container."""
    return SequentialAgent(
        name="leadslayer_pipeline",
        sub_agents=[
            AuditorAgent(name="market_auditor", callbacks=callbacks, client=client),
            ICPAgent(name="icp_engine", callbacks=callbacks, client=client, memory_store=memory_store),
            HunterSwarmAgent(name="hunter_swarm", callbacks=callbacks, client=client, memory_store=memory_store),
            SlayerSwarmAgent(name="slayer_swarm", callbacks=callbacks, client=client),
            SniperAgent(name="sniper_agent", callbacks=callbacks, client=client, memory_store=memory_store),
        ],
    )
