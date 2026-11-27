from __future__ import annotations

import os
from collections import Counter
from collections.abc import AsyncIterator
from typing import Any

from google import genai
from google.adk.agents import BaseAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from pydantic import ConfigDict

from app.agents.auditor_agent import MarketAuditorADKAgent
from app.agents.hunter_agent import HunterSwarmADKAgent
from app.agents.icp_agent import ICPEngineADKAgent
from app.agents.interface import PipelineCallbacks, PipelineFinalResult
from app.agents.key_rotator import key_rotator
from app.agents.mcp_action_agent import McpActionADKAgent
from app.agents.slayer_agent import SlayerSwarmADKAgent, execute_slayer_swarm
from app.agents.sniper_agent import SniperADKAgent
from app.config import settings
from app.memory.vector_store import HybridMatchContext
from app.models.schemas import (
    EmailDraft,
    HunterReport,
    ICPProfile,
    LeadRecord,
    MarketAuditResult,
    MCPToolCallRecord,
    SlayerVerdict,
    SlayingLevel,
    StartupInput,
)


async def maybe_recover_zero_survivors(
    startup: StartupInput,
    audit: MarketAuditResult,
    leads: list[LeadRecord],
    priors: dict[str, HybridMatchContext],
    verdicts: dict[str, SlayerVerdict],
    callbacks: PipelineCallbacks,
    client: Any | None = None,
) -> tuple[StartupInput, dict[str, SlayerVerdict]]:
    """
    Adaptive Zero-Survivor Recovery Guardrail:
    If Slayer kills 100% of leads under RUTHLESS or NORMAL, diagnoses the bottleneck
    and automatically relaxes one aggression tier so the pipeline self-heals.
    """
    survived_n = sum(1 for v in verdicts.values() if v.survived)
    if survived_n > 0 or not leads:
        return startup, verdicts

    if startup.slaying_level == SlayingLevel.RUTHLESS:
        next_level = SlayingLevel.NORMAL
    elif startup.slaying_level == SlayingLevel.NORMAL:
        next_level = SlayingLevel.LENIENT
    else:
        return startup, verdicts

    counts = Counter(
        v.rejection_category.value
        for v in verdicts.values()
        if v.rejection_category is not None
    )
    top_blocker, top_n = counts.most_common(1)[0] if counts else ("NO_URGENCY_SIGNAL", len(verdicts))

    await callbacks.on_log(
        f"[RecoveryCoordinator] 0/{len(leads)} survived under {startup.slaying_level.value} "
        f"(primary bottleneck: {top_blocker} x{top_n}). Adapting strategy -> relaxing to {next_level.value} and re-evaluating..."
    )
    relaxed_startup = startup.model_copy(update={"slaying_level": next_level})
    recovered_verdicts = await execute_slayer_swarm(
        relaxed_startup,
        audit,
        leads,
        priors,
        callbacks,
        client=client,
    )
    return relaxed_startup, recovered_verdicts


class RecoveryCoordinatorADKAgent(BaseAgent):
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
        verdicts = {
            lid: SlayerVerdict.model_validate(raw)
            for lid, raw in ctx.session.state.get("verdicts", {}).items()
        }
        updated_startup, updated_verdicts = await maybe_recover_zero_survivors(
            startup, audit, leads, priors, verdicts, self.callbacks
        )
        startup_dict = updated_startup.model_dump(mode="json", exclude={"leads"})
        verdicts_dict = {lid: v.model_dump(mode="json") for lid, v in updated_verdicts.items()}
        ctx.session.state["startup_input"] = startup_dict
        ctx.session.state["verdicts"] = verdicts_dict
        survived_n = sum(1 for v in updated_verdicts.values() if v.survived)
        yield Event(
            author=self.name,
            content=genai.types.Content(
                role="model",
                parts=[
                    genai.types.Part.from_text(
                        text=f"Recovery check complete ({survived_n} survivors at {updated_startup.slaying_level.value})"
                    )
                ],
            ),
            actions=EventActions(
                state_delta={
                    "startup_input": startup_dict,
                    "verdicts": verdicts_dict,
                }
            ),
        )


async def run_live_pipeline(
    run_id: str,
    startup_input: StartupInput,
    leads: list[LeadRecord],
    callbacks: PipelineCallbacks,
) -> PipelineFinalResult:
    """
    Executes the autonomous Google ADK 2.0 multi-agent pipeline:
    MarketAuditor (adaptive tools) -> ICPEngine -> HunterSwarm -> SlayerSwarm
    -> RecoveryCoordinator (self-healing) -> Sniper -> OutreachMCPCoordinator (McpToolset).
    """
    active_key = key_rotator.next_key() or settings.gemini_api_key
    if active_key:
        os.environ["GOOGLE_API_KEY"] = active_key

    pipeline_agent = SequentialAgent(
        name="leadslayer_gtm_pipeline",
        sub_agents=[
            MarketAuditorADKAgent(name="market_auditor_step", callbacks=callbacks),
            ICPEngineADKAgent(name="icp_engine_step", run_id=run_id, callbacks=callbacks),
            HunterSwarmADKAgent(name="hunter_swarm_step", run_id=run_id, callbacks=callbacks),
            SlayerSwarmADKAgent(name="slayer_swarm_step", callbacks=callbacks),
            RecoveryCoordinatorADKAgent(name="recovery_coordinator_step", callbacks=callbacks),
            SniperADKAgent(name="sniper_step", run_id=run_id, callbacks=callbacks),
            McpActionADKAgent(name="mcp_action_step", run_id=run_id, callbacks=callbacks),
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
    mcp_tool_calls = [
        MCPToolCallRecord.model_validate(item)
        for item in state.get("mcp_tool_calls", [])
    ]

    return PipelineFinalResult(
        run_id=run_id,
        market_audit=audit,
        icps=icps,
        hunter_report=hunter_report,
        verdicts=verdicts,
        emails=emails,
        mcp_tool_calls=mcp_tool_calls,
    )
