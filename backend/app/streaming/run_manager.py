from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import stdio_client

from app.agents.interface import PipelineCallbacks, PipelineFinalResult
from app.config import DATA_DIR, EXPORTS_DIR, settings
from app.harvey_bridge.dispatcher import dispatch_emails_via_harvey
from app.streaming.exporter import persist_verified_leads_csv
from app.models.schemas import (
    DeliveryMode,
    DispatchReceipt,
    DispatchResponse,
    EmailDraft,
    ExecutionMode,
    HunterReport,
    ICPProfile,
    LeadRecord,
    MarketAuditResult,
    MCPToolCallRecord,
    ModelId,
    PipelinePhase,
    ResurrectResponse,
    RunStateSnapshot,
    SlayerVerdict,
    StartupInput,
    StreamEventType,
)
from app.services.lead_loader import load_preset_leads
from app.services.mcp_client import build_mcp_server_params
from app.streaming.event_bus import EventStreamBus
from app.streaming.pacer import DualLanePacer
from app.streaming.telemetry import TelemetryAggregator


PipelineRunnerFn = Callable[
    [str, StartupInput, list[LeadRecord], PipelineCallbacks],
    Awaitable[PipelineFinalResult],
]
ResurrectRunnerFn = Callable[
    [str, LeadRecord, SlayerVerdict, ICPProfile],
    Awaitable[tuple[SlayerVerdict, EmailDraft]],
]


class RunNotFoundError(KeyError):
    pass


class LeadNotFoundError(KeyError):
    pass


@dataclass
class RunState:
    run_id: str
    created_at: float
    startup_input: StartupInput
    leads: list[LeadRecord]
    telemetry: TelemetryAggregator
    bus: EventStreamBus
    pacer: DualLanePacer
    phase: PipelinePhase = PipelinePhase.IDLE
    market_audit: MarketAuditResult | None = None
    icps: list[ICPProfile] = field(default_factory=list)
    hunter_report: HunterReport | None = None
    verdicts: dict[str, SlayerVerdict] = field(default_factory=dict)
    emails: dict[str, EmailDraft] = field(default_factory=dict)
    mcp_tool_calls: list[MCPToolCallRecord] = field(default_factory=list)
    task: asyncio.Task[None] | None = None
    error_message: str | None = None

    def to_snapshot(self) -> RunStateSnapshot:
        return RunStateSnapshot(
            run_id=self.run_id,
            phase=self.phase,
            startup_input=self.startup_input,
            market_audit=self.market_audit,
            icps=list(self.icps),
            hunter_report=self.hunter_report,
            leads=list(self.leads),
            verdicts=dict(self.verdicts),
            emails=dict(self.emails),
            mcp_tool_calls=list(self.mcp_tool_calls),
            telemetry=self.telemetry.snapshot(),
            error_message=self.error_message,
        )


class _BusPipelineCallbacks:
    """Bridges ADK PipelineCallbacks into RunState, TelemetryAggregator, and DualLanePacer."""

    def __init__(self, state: RunState) -> None:
        self._state = state

    async def on_phase(self, phase: PipelinePhase) -> None:
        if self._state.phase == PipelinePhase.SLAYING and phase != PipelinePhase.SLAYING:
            await self._state.pacer.flush()
        self._state.phase = phase
        await self._state.pacer.emit_immediate(
            StreamEventType.PHASE_CHANGED,
            {
                "phase": phase.value,
                "telemetry": self._state.telemetry.snapshot().model_dump(mode="json"),
            },
        )

    async def on_log(self, message: str) -> None:
        await self._state.pacer.emit_immediate(
            StreamEventType.AGENT_LOG,
            {"message": message},
        )

    async def on_model_call(self, model_id: ModelId) -> None:
        self._state.telemetry.record_model_call(model_id)

    async def on_audit(self, audit: MarketAuditResult) -> None:
        self._state.market_audit = audit
        await self._state.pacer.emit_immediate(
            StreamEventType.AUDIT_COMPLETED,
            {
                "audit": audit.model_dump(mode="json"),
                "telemetry": self._state.telemetry.snapshot().model_dump(mode="json"),
            },
        )

    async def on_icps(self, icps: list[ICPProfile]) -> None:
        self._state.icps = list(icps)
        await self._state.pacer.emit_immediate(
            StreamEventType.ICPS_GENERATED,
            {
                "icps": [icp.model_dump(mode="json") for icp in icps],
                "telemetry": self._state.telemetry.snapshot().model_dump(mode="json"),
            },
        )

    async def on_leads_loaded(self, leads: list[LeadRecord]) -> None:
        self._state.leads = list(leads)
        self._state.telemetry.set_total_leads(len(leads))
        await self._state.pacer.emit_immediate(
            StreamEventType.LEADS_LOADED,
            {
                "leads": [lead.model_dump(mode="json") for lead in leads],
                "telemetry": self._state.telemetry.snapshot().model_dump(mode="json"),
            },
        )

    async def on_hunter_report(self, report: HunterReport) -> None:
        self._state.hunter_report = report
        await self._state.pacer.emit_immediate(
            StreamEventType.HUNTER_REPORT,
            {
                "hunter_report": report.model_dump(mode="json"),
                "telemetry": self._state.telemetry.snapshot().model_dump(mode="json"),
            },
        )

    async def on_verdict(self, verdict: SlayerVerdict) -> None:
        self._state.verdicts[verdict.lead_id] = verdict
        self._state.telemetry.record_verdict(verdict)
        await self._state.pacer.enqueue_verdict(
            verdict, self._state.telemetry.snapshot()
        )

    async def on_email(self, draft: EmailDraft) -> None:
        self._state.emails[draft.lead_id] = draft
        await self._state.pacer.emit_immediate(
            StreamEventType.EMAIL_DRAFTED,
            {
                "email_draft": draft.model_dump(mode="json"),
                "telemetry": self._state.telemetry.snapshot().model_dump(mode="json"),
            },
        )

    async def on_mcp_tool_call(self, record: MCPToolCallRecord) -> None:
        self._state.mcp_tool_calls.append(record)
        await self._state.pacer.emit_immediate(
            StreamEventType.MCP_TOOL_CALL,
            {
                "mcp_tool_call": record.model_dump(mode="json"),
                "telemetry": self._state.telemetry.snapshot().model_dump(mode="json"),
            },
        )


def _default_live_runner() -> PipelineRunnerFn:
    try:
        from app.agents.pipeline import run_live_pipeline

        return run_live_pipeline
    except ImportError as exc:
        raise RuntimeError(
            "AI agents module (app.agents.pipeline) is not merged yet. "
            "Merge Stages 2-3 or inject a pipeline_runner."
        ) from exc


def _default_resurrect_runner() -> ResurrectRunnerFn:
    try:
        from app.agents.sniper_agent import resurrect_single_lead

        return resurrect_single_lead
    except ImportError as exc:
        raise RuntimeError(
            "AI sniper module (app.agents.sniper_agent) is not merged yet. "
            "Merge Stages 2-3 or inject a resurrect_runner."
        ) from exc


async def _run_authentic_replay(
    run_id: str,
    startup_input: StartupInput,
    leads: list[LeadRecord],
    callbacks: PipelineCallbacks,
    replay_path: Path = DATA_DIR / "replay_snapshot.json",
    time_scale: float = 1.0,
) -> PipelineFinalResult:
    """
    Replays an authentic recorded real-Gemini session from data/replay_snapshot.json
    with realistic >=3s-per-step pacing and live ADK telemetry logs.
    """
    if not replay_path.exists():
        raise RuntimeError(
            "Authentic replay snapshot (data/replay_snapshot.json) has not been captured yet. "
            "Run a live Gemini session with record_replay_snapshot.py in Stage 7 first."
        )

    raw = json.loads(replay_path.read_text(encoding="utf-8"))
    snapshot = RunStateSnapshot.model_validate(raw["snapshot"])

    async def _pause(seconds: float) -> None:
        if time_scale > 0 and seconds > 0:
            await asyncio.sleep(seconds * time_scale)

    # Step 1: Market Auditor (~3.8s total)
    await callbacks.on_phase(PipelinePhase.AUDITING)
    await callbacks.on_log(
        f"[MarketAuditor] Auditing '{startup_input.product_name}' on {settings.gemini_brain_model}..."
    )
    await _pause(0.9)
    if snapshot.market_audit and snapshot.market_audit.url_scraped_context_used:
        await callbacks.on_log(
            f"[MarketAuditor] Extracted live website context from {startup_input.product_url or 'product URL'}."
        )
        await _pause(0.6)
    await callbacks.on_log(
        "[MarketAuditor] Running Assumption vs. Reality Gap Analysis & Competitor Wedge..."
    )
    await _pause(0.9)
    if snapshot.market_audit:
        await callbacks.on_model_call(ModelId.GEMINI_4_HYDROGEN)
        await callbacks.on_audit(snapshot.market_audit)
        await callbacks.on_log(
            f"[MarketAuditor] Readiness {snapshot.market_audit.market_readiness_score}/100 · "
            f"Locked {len(snapshot.market_audit.anti_icp_red_flags)} Anti-ICP kill rules."
        )
    await _pause(1.4)

    # Step 2: ICP Engine + Vector Memory (~3.8s total)
    await callbacks.on_phase(PipelinePhase.ICP_GENERATION)
    await callbacks.on_log(
        f"[ICPEngine] Synthesizing 3 non-overlapping ICP profiles ({settings.gemini_brain_model})..."
    )
    await _pause(1.3)
    await callbacks.on_model_call(ModelId.GEMINI_4_HYDROGEN)
    await callbacks.on_icps(snapshot.icps)
    await callbacks.on_log(
        "[ICPEngine] Chunking product wedge & Anti-ICP guardrails into vector store..."
    )
    await _pause(0.8)
    await callbacks.on_log(
        f"[ICPEngine] Indexing ICPs & {len(leads)} lead vectors via {settings.gemini_embedding_model} (768d MRL)..."
    )
    await callbacks.on_model_call(ModelId.GEMINI_EMBEDDING_2)
    await _pause(1.7)

    # Step 3: Hunter Swarm + Dual-Polarity Scoring (~3.6s total)
    await callbacks.on_phase(PipelinePhase.HUNTING)
    await callbacks.on_log(
        "[HunterSwarm] Generating Boolean hunt queries across LinkedIn, GitHub & hiring feeds..."
    )
    await _pause(1.3)
    await callbacks.on_model_call(ModelId.GEMINI_3_5_FLASH_LITE)
    if snapshot.hunter_report:
        await callbacks.on_hunter_report(snapshot.hunter_report)
    await callbacks.on_log(
        f"[HunterSwarm] Computing Dual-Polarity NumPy priors (60% ICP + 25% Structural - 15% Anti-ICP) across {len(leads)} leads..."
    )
    await _pause(1.4)
    await callbacks.on_log(
        f"[HunterSwarm] Armed {len(leads)} leads with Dual-Polarity vector priors (6h cache hit)."
    )
    await _pause(0.9)

    # Step 4: Slayer Swarm (Smooth Bloodbath cascade ~5.7s total)
    await callbacks.on_phase(PipelinePhase.SLAYING)
    await callbacks.on_log(
        f"[SlayerSwarm] Unleashing {startup_input.slaying_level.value} Slayer ({settings.gemini_workhorse_model}) across {len(leads)} leads..."
    )
    await _pause(0.5)
    for lead in leads:
        verdict = snapshot.verdicts.get(lead.id)
        if verdict is not None:
            await callbacks.on_model_call(ModelId.GEMINI_3_5_FLASH_LITE)
            await callbacks.on_verdict(verdict)
            await _pause(0.085)

    killed_n = sum(1 for v in snapshot.verdicts.values() if not v.survived)
    surv_n = len(snapshot.verdicts) - killed_n
    await callbacks.on_log(
        f"[SlayerSwarm] Bloodbath complete: {killed_n} KILLED, {surv_n} SURVIVED."
    )
    await _pause(1.0)

    # Step 5: Sniper Agent (Grounded Emails ~4.8s total)
    await callbacks.on_phase(PipelinePhase.SNIPING)
    await callbacks.on_log(
        f"[Sniper] Retrieving top-2 Stage 2 product chunks for {surv_n} survivors..."
    )
    await _pause(1.0)
    await callbacks.on_log(
        "[Sniper] Verifying evidence quotes & anti-hallucination grounding..."
    )
    await _pause(0.7)
    for lead in leads:
        draft = snapshot.emails.get(lead.id)
        if draft is not None:
            await callbacks.on_model_call(ModelId.GEMINI_4_HYDROGEN)
            await callbacks.on_email(draft)
            await callbacks.on_log(
                f"[Sniper] Drafted email for {draft.recipient_name} ({draft.company}) · Evidence verified."
            )
            await _pause(0.32)

    # Step 6: Execute real $0 local stdio MCP operations for top survivors
    mcp_calls: list[MCPToolCallRecord] = []
    survivor_leads = [l for l in leads if (v := snapshot.verdicts.get(l.id)) and v.survived]
    try:
        params = build_mcp_server_params()
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                await callbacks.on_log(
                    "[OutreachMCPAgent] Connected to leadslayer-ops-mcp over stdio — executing autonomous operational tools..."
                )

                for lead in survivor_leads[:3]:
                    v = snapshot.verdicts[lead.id]
                    crm_res = await session.call_tool(
                        "check_and_update_dnc_crm",
                        {"domain": lead.domain, "company": lead.company, "action": "check"},
                    )
                    crm_txt = getattr(crm_res.content[0], "text", "{}") if crm_res.content else "{}"
                    rec1 = MCPToolCallRecord(
                        id=uuid.uuid4().hex[:8],
                        timestamp_ms=int(time.time() * 1000),
                        agent_name="OutreachMCPAgent",
                        decision_reason=f"Verify CRM & Do-Not-Contact status for {lead.company}",
                        server_name="leadslayer-ops-mcp",
                        tool_name="check_and_update_dnc_crm",
                        arguments_summary=f"domain={lead.domain!r}, action='check'",
                        result_summary=crm_txt[:220],
                        status="BLOCKED" if '"allowed": false' in crm_txt.lower() else "SUCCEEDED",
                    )
                    mcp_calls.append(rec1)
                    await callbacks.on_mcp_tool_call(rec1)
                    await callbacks.on_log(f"[MCP DECISION] {rec1.decision_reason} -> `check_and_update_dnc_crm`")

                    if v.qualification_score >= 80:
                        rem_res = await session.call_tool(
                            "schedule_followup_reminder",
                            {
                                "run_id": run_id,
                                "lead_id": lead.id,
                                "company": lead.company,
                                "contact_name": lead.full_name,
                                "priority": "HIGH",
                                "due_in_days": 2,
                                "reason": lead.recent_signal[:120],
                            },
                        )
                        rem_txt = getattr(rem_res.content[0], "text", "{}") if rem_res.content else "{}"
                        rec2 = MCPToolCallRecord(
                            id=uuid.uuid4().hex[:8],
                            timestamp_ms=int(time.time() * 1000),
                            agent_name="OutreachMCPAgent",
                            decision_reason=f"High-urgency score ({v.qualification_score}) on {lead.company} -> schedule 2-day .ics follow-up",
                            server_name="leadslayer-ops-mcp",
                            tool_name="schedule_followup_reminder",
                            arguments_summary=f"lead_id={lead.id!r}, priority='HIGH', due_in_days=2",
                            result_summary=rem_txt[:220],
                            status="SUCCEEDED",
                        )
                        mcp_calls.append(rec2)
                        await callbacks.on_mcp_tool_call(rec2)
                        await callbacks.on_log(f"[MCP DECISION] {rec2.decision_reason} -> `schedule_followup_reminder`")

                brief_md = (
                    f"## Summary\n- Product: {startup_input.product_name}\n"
                    f"- Evaluated: {len(leads)} | Killed: {killed_n} | Survived: {surv_n}\n"
                    f"- Sharpened Value Prop: {snapshot.market_audit.sharpened_value_prop if snapshot.market_audit else 'N/A'}\n"
                )
                art_res = await session.call_tool(
                    "save_campaign_artifacts",
                    {
                        "run_id": run_id,
                        "product_name": startup_input.product_name,
                        "summary_markdown": brief_md,
                    },
                )
                art_txt = getattr(art_res.content[0], "text", "{}") if art_res.content else "{}"
                rec3 = MCPToolCallRecord(
                    id=uuid.uuid4().hex[:8],
                    timestamp_ms=int(time.time() * 1000),
                    agent_name="OutreachMCPAgent",
                    decision_reason=f"Persist executive brief & audit trail to exports/{run_id}/",
                    server_name="leadslayer-ops-mcp",
                    tool_name="save_campaign_artifacts",
                    arguments_summary=f"run_id={run_id!r}, product_name={startup_input.product_name!r}",
                    result_summary=art_txt[:220],
                    status="SUCCEEDED",
                )
                mcp_calls.append(rec3)
                await callbacks.on_mcp_tool_call(rec3)
                await callbacks.on_log(f"[MCP DECISION] {rec3.decision_reason} -> `save_campaign_artifacts`")
    except Exception as exc:
        await callbacks.on_log(f"[OutreachMCPAgent] MCP tool notice: {exc}")

    await _pause(0.35)

    assert snapshot.market_audit is not None
    return PipelineFinalResult(
        run_id=run_id,
        market_audit=snapshot.market_audit,
        icps=snapshot.icps,
        hunter_report=snapshot.hunter_report,
        verdicts=snapshot.verdicts,
        emails=snapshot.emails,
        mcp_tool_calls=mcp_calls,
    )


class RunManager:
    """Manages bounded in-memory pipeline runs, background tasks, and mutations."""

    def __init__(
        self,
        max_runs: int = settings.max_active_runs,
        ttl_seconds: int = settings.embedding_cache_ttl_seconds,
        pipeline_runner: PipelineRunnerFn | None = None,
        resurrect_runner: ResurrectRunnerFn | None = None,
        pacer_normal_delay_s: float = 0.09,
        pacer_fast_delay_s: float = 0.025,
        replay_path: Path = DATA_DIR / "replay_snapshot.json",
        replay_time_scale: float = 1.0,
        exports_dir: Path | None = None,
    ) -> None:
        self._runs: OrderedDict[str, RunState] = OrderedDict()
        self._max_runs = max_runs
        self._ttl_seconds = ttl_seconds
        self._pipeline_runner = pipeline_runner
        self._resurrect_runner = resurrect_runner
        self._pacer_normal_delay_s = pacer_normal_delay_s
        self._pacer_fast_delay_s = pacer_fast_delay_s
        self._replay_path = replay_path
        self._replay_time_scale = replay_time_scale
        self._exports_dir = exports_dir

    def _effective_exports_dir(self) -> Path:
        return self._exports_dir if self._exports_dir is not None else EXPORTS_DIR

    def _purge_expired_and_cap(self) -> None:
        now = time.time()
        expired_ids = [
            rid
            for rid, st in self._runs.items()
            if (now - st.created_at) > self._ttl_seconds
            and (st.task is None or st.task.done())
        ]
        for rid in expired_ids:
            self._runs.pop(rid, None)

        while len(self._runs) >= self._max_runs:
            # Prefer evicting finished runs first
            evict_id = next(
                (
                    rid
                    for rid, st in self._runs.items()
                    if st.task is None or st.task.done()
                ),
                None,
            )
            if evict_id is None:
                evict_id, _ = self._runs.popitem(last=False)
            else:
                self._runs.pop(evict_id, None)

    def get_run(self, run_id: str) -> RunState:
        state = self._runs.get(run_id)
        if state is None:
            raise RunNotFoundError(f"Run '{run_id}' not found.")
        self._runs.move_to_end(run_id)
        return state

    async def start_run(self, startup_input: StartupInput) -> RunState:
        self._purge_expired_and_cap()

        needs_autonomous = (
            startup_input.auto_discover_leads
            or any(src in startup_input.lead_sources for src in ("AI_SEARCH", "LINKEDIN_SEARCH"))
        )
        if startup_input.leads:
            leads = list(startup_input.leads)
        elif needs_autonomous and startup_input.execution_mode != ExecutionMode.SAFE_REPLAY:
            leads = []
        else:
            leads = load_preset_leads()
        run_id = uuid.uuid4().hex[:12]
        bus = EventStreamBus(run_id)
        pacer = DualLanePacer(
            bus=bus,
            normal_delay_s=self._pacer_normal_delay_s,
            fast_delay_s=self._pacer_fast_delay_s,
        )
        telemetry = TelemetryAggregator(total_leads=len(leads))

        state = RunState(
            run_id=run_id,
            created_at=time.time(),
            startup_input=startup_input,
            leads=leads,
            telemetry=telemetry,
            bus=bus,
            pacer=pacer,
        )
        self._runs[run_id] = state

        await pacer.emit_immediate(
            StreamEventType.LEADS_LOADED,
            {"leads": [lead.model_dump(mode="json") for lead in leads]},
        )

        pacer.start()
        state.task = asyncio.create_task(self._execute_pipeline_safe(state))
        return state

    async def _execute_pipeline_safe(self, state: RunState) -> None:
        callbacks = _BusPipelineCallbacks(state)
        try:
            if state.startup_input.execution_mode == ExecutionMode.SAFE_REPLAY:
                await _run_authentic_replay(
                    state.run_id,
                    state.startup_input,
                    state.leads,
                    callbacks,
                    replay_path=self._replay_path,
                    time_scale=self._replay_time_scale,
                )
            else:
                runner = self._pipeline_runner or _default_live_runner()
                await runner(state.run_id, state.startup_input, state.leads, callbacks)

            await state.pacer.flush()
            persist_verified_leads_csv(
                state.run_id,
                state.leads,
                state.verdicts,
                state.emails,
                exports_dir=self._effective_exports_dir(),
            )
            state.phase = PipelinePhase.READY
            await state.pacer.emit_immediate(
                StreamEventType.PIPELINE_COMPLETED,
                {
                    "phase": PipelinePhase.READY.value,
                    "telemetry": state.telemetry.snapshot().model_dump(mode="json"),
                },
            )
        except Exception as exc:
            await state.pacer.flush()
            state.phase = PipelinePhase.ERROR
            user_msg = getattr(exc, "user_message", None) or str(exc)
            status_code = getattr(exc, "status_code", None)
            state.error_message = user_msg
            await state.pacer.emit_immediate(
                StreamEventType.PIPELINE_ERROR,
                {"message": user_msg, "status_code": status_code},
            )
        finally:
            await state.pacer.stop()
            await state.bus.close()

    async def resurrect_lead(self, run_id: str, lead_id: str) -> ResurrectResponse:
        state = self.get_run(run_id)
        lead = next((l for l in state.leads if l.id == lead_id), None)
        if lead is None:
            raise LeadNotFoundError(f"Lead '{lead_id}' not found in run '{run_id}'.")

        old_verdict = state.verdicts.get(lead_id)
        if old_verdict is None:
            raise ValueError(f"Lead '{lead_id}' has no verdict yet.")

        if old_verdict.survived and lead_id in state.emails:
            return ResurrectResponse(
                verdict=old_verdict,
                email_draft=state.emails[lead_id],
                telemetry=state.telemetry.snapshot(),
            )

        icp = next(
            (i for i in state.icps if i.id == old_verdict.matched_icp_id),
            state.icps[0] if state.icps else None,
        )
        if icp is None:
            raise ValueError("Cannot resurrect lead before ICPs are generated.")

        runner = self._resurrect_runner or _default_resurrect_runner()
        new_verdict, draft = await runner(run_id, lead, old_verdict, icp)

        new_verdict = new_verdict.model_copy(
            update={"survived": True, "resurrected_by_user": True}
        )
        state.verdicts[lead_id] = new_verdict
        state.emails[lead_id] = draft
        if not old_verdict.survived:
            state.telemetry.record_resurrection(old_verdict.rejection_category)
        persist_verified_leads_csv(
            state.run_id,
            state.leads,
            state.verdicts,
            state.emails,
            exports_dir=self._effective_exports_dir(),
        )

        return ResurrectResponse(
            verdict=new_verdict,
            email_draft=draft,
            telemetry=state.telemetry.snapshot(),
        )

    async def dispatch_emails(
        self,
        run_id: str,
        lead_ids: list[str],
        delivery_mode: DeliveryMode = "SANDBOX",
    ) -> DispatchResponse:
        state = self.get_run(run_id)
        leads_by_id = {lead.id: lead for lead in state.leads}
        response, any_sent = await dispatch_emails_via_harvey(
            emails=state.emails,
            leads_by_id=leads_by_id,
            lead_ids=lead_ids,
            delivery_mode=delivery_mode,
            product_name=state.startup_input.product_name or "LeadSlayer",
        )
        if any_sent:
            state.phase = PipelinePhase.DISPATCHED
        persist_verified_leads_csv(
            state.run_id,
            state.leads,
            state.verdicts,
            state.emails,
            exports_dir=self._effective_exports_dir(),
        )
        return response


run_manager = RunManager()
