from __future__ import annotations

import os
from google import genai
from google.adk.agents import SequentialAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from app.agents.auditor_agent import MarketAuditorADKAgent
from app.agents.hunter_agent import HunterSwarmADKAgent
from app.agents.icp_agent import ICPEngineADKAgent
from app.agents.interface import PipelineCallbacks, PipelineFinalResult
from app.agents.slayer_agent import SlayerSwarmADKAgent
from app.agents.sniper_agent import SniperADKAgent
from app.config import settings
from app.models.schemas import (
    EmailDraft,
    HunterReport,
    ICPProfile,
    LeadRecord,
    MarketAuditResult,
    SlayerVerdict,
    StartupInput,
)


async def run_live_pipeline(
    run_id: str,
    startup_input: StartupInput,
    leads: list[LeadRecord],
    callbacks: PipelineCallbacks,
) -> PipelineFinalResult:
    """
    Executes the full 5-step Google ADK 2.0 SequentialAgent pipeline:
    MarketAuditor -> ICPEngine -> HunterSwarm -> SlayerSwarm -> Sniper.
    """
    if settings.gemini_api_key:
        os.environ["GOOGLE_API_KEY"] = settings.gemini_api_key

    pipeline_agent = SequentialAgent(
        name="leadslayer_gtm_pipeline",
        sub_agents=[
            MarketAuditorADKAgent(name="market_auditor_step", callbacks=callbacks),
            ICPEngineADKAgent(name="icp_engine_step", run_id=run_id, callbacks=callbacks),
            HunterSwarmADKAgent(name="hunter_swarm_step", run_id=run_id, callbacks=callbacks),
            SlayerSwarmADKAgent(name="slayer_swarm_step", callbacks=callbacks),
            SniperADKAgent(name="sniper_step", run_id=run_id, callbacks=callbacks),
        ],
    )

    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="leadslayer_adk",
        user_id="founder",
        session_id=run_id,
        state={
            "startup_input": startup_input.model_dump(mode="json", exclude={"leads"}),
            "leads": [lead.model_dump(mode="json") for lead in leads],
        },
    )

    runner = Runner(
        app_name="leadslayer_adk",
        agent=pipeline_agent,
        session_service=session_service,
    )
    kickoff_msg = genai.types.Content(
        role="user",
        parts=[
            genai.types.Part.from_text(
                text=f"Execute LeadSlayer GTM pipeline for {startup_input.product_name} ({startup_input.slaying_level.value})."
            )
        ],
    )

    async for _ in runner.run_async(
        user_id="founder",
        session_id=run_id,
        new_message=kickoff_msg,
    ):
        pass

    final_session = await session_service.get_session(
        app_name="leadslayer_adk",
        user_id="founder",
        session_id=run_id,
    )
    state = final_session.state if final_session else {}

    audit = MarketAuditResult.model_validate(state["market_audit"])
    icps = [ICPProfile.model_validate(item) for item in state["icps"]]
    hunter_report = (
        HunterReport.model_validate(state["hunter_report"])
        if state.get("hunter_report")
        else None
    )
    verdicts = {
        lid: SlayerVerdict.model_validate(raw)
        for lid, raw in state.get("verdicts", {}).items()
    }
    emails = {
        lid: EmailDraft.model_validate(raw)
        for lid, raw in state.get("emails", {}).items()
    }

    return PipelineFinalResult(
        run_id=run_id,
        market_audit=audit,
        icps=icps,
        hunter_report=hunter_report,
        verdicts=verdicts,
        emails=emails,
    )
