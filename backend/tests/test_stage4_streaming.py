from __future__ import annotations

import asyncio
import csv
import io
import json
import time

import httpx
from fastapi import FastAPI

from app.agents.interface import PipelineCallbacks, PipelineFinalResult
from app.models.schemas import (
    AssumptionGap,
    CompetitorInsight,
    EmailDraft,
    HunterReport,
    HuntQuery,
    ICPProfile,
    LeadRecord,
    MarketAuditResult,
    ModelId,
    PipelinePhase,
    ReadinessBreakdown,
    RejectionCategory,
    SlayerVerdict,
    StartupInput,
    StreamEventType,
)
from app.routers.pipeline_router import create_pipeline_router
from app.services.lead_loader import load_default_startup, load_preset_leads
from app.streaming.event_bus import EventStreamBus
from app.streaming.pacer import DualLanePacer
from app.streaming.run_manager import RunManager
from app.streaming.telemetry import TelemetryAggregator


class _FakeGeminiUnavailableError(Exception):
    def __init__(self, user_message: str, status_code: int = 429) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.status_code = status_code


def _build_test_audit() -> MarketAuditResult:
    return MarketAuditResult(
        market_reality_summary="Cloud teams on EKS/GKE waste 35% of compute.",
        founder_blind_spots=["Not every tech company runs Kubernetes."],
        sharpened_value_prop="Autonomous FinOps guardrail for Series A-C EKS teams.",
        anti_icp_red_flags=["Datadog CCM multi-year lock-in", "<15 employees"],
        market_readiness_score=84,
        url_scraped_context_used=True,
        search_grounding_used=False,
        assumption_gaps=[
            AssumptionGap(
                founder_belief="Any cloud CTO needs us",
                market_reality="Only K8s teams >30 devs feel autoscaling cost pain",
                severity="HIGH",
                strategic_fix="Target Series A-C EKS/GKE teams with GPU/pod spikes",
            )
        ],
        competitor_landscape=[
            CompetitorInsight(
                name="Datadog CCM",
                positioning_weakness="Expensive bundled APM lock-in",
                switching_trigger="Renewal sticker shock",
            )
        ],
        buying_objections=[],
        readiness_breakdown=ReadinessBreakdown(
            pain_urgency=90, icp_clarity=85, differentiation=82, timing_fit=80
        ),
    )


def _build_test_icps() -> list[ICPProfile]:
    return [
        ICPProfile(
            id="icp_1",
            name="Series B EKS CTO",
            target_roles=["CTO", "VP of Engineering"],
            min_employees=40,
            max_employees=300,
            required_tech_signals=["AWS", "EKS", "Kubernetes"],
            buying_triggers=["AWS bill jumped 3x"],
            instant_disqualifiers=["Datadog Cloud Cost contract"],
            vector_doc_id="icp_1",
        )
    ]


async def _mock_pipeline_runner(
    run_id: str,
    startup_input: StartupInput,
    leads: list[LeadRecord],
    callbacks: PipelineCallbacks,
) -> PipelineFinalResult:
    await callbacks.on_phase(PipelinePhase.AUDITING)
    await callbacks.on_model_call(ModelId.GEMINI_4_HYDROGEN)
    audit = _build_test_audit()
    await callbacks.on_audit(audit)

    await callbacks.on_phase(PipelinePhase.ICP_GENERATION)
    await callbacks.on_model_call(ModelId.GEMINI_4_HYDROGEN)
    await callbacks.on_model_call(ModelId.GEMINI_EMBEDDING_2)
    icps = _build_test_icps()
    await callbacks.on_icps(icps)

    await callbacks.on_phase(PipelinePhase.HUNTING)
    await callbacks.on_hunter_report(
        HunterReport(
            hunt_queries=[
                HuntQuery(
                    source="LinkedIn + Tech Radar",
                    query_string='CTO "AWS EKS" "cost spike"',
                    signal_target="Runaway K8s spend",
                )
            ],
            enriched_sparse_leads=0,
            url_fetches_succeeded=1,
            total_leads_ready=len(leads),
        )
    )

    await callbacks.on_phase(PipelinePhase.SLAYING)
    verdicts: dict[str, SlayerVerdict] = {}
    for idx, lead in enumerate(leads):
        survived = idx < 8
        verdict = SlayerVerdict(
            lead_id=lead.id,
            survived=survived,
            rejection_category=None if survived else RejectionCategory.COMPETITOR_LOCK_IN,
            headline_tag="SURVIVED: EKS Cost Spike" if survived else "KILLED: Datadog Lock-In",
            reasoning="Clear fit" if survived else "Signed 3-year Datadog CCM contract",
            matched_icp_id="icp_1" if survived else None,
            icp_similarity_score=0.91 if survived else 0.42,
            anti_icp_similarity_score=0.12 if survived else 0.85,
            structural_match_score=0.88 if survived else 0.30,
            qualification_score=92 if survived else 24,
            confidence=0.94,
            slaying_level_applied=startup_input.slaying_level,
            latency_ms=110,
        )
        verdicts[lead.id] = verdict
        await callbacks.on_model_call(ModelId.GEMINI_3_5_FLASH_LITE)
        await callbacks.on_verdict(verdict)

    await callbacks.on_phase(PipelinePhase.SNIPING)
    emails: dict[str, EmailDraft] = {}
    for lead in leads[:8]:
        await callbacks.on_model_call(ModelId.GEMINI_4_HYDROGEN)
        draft = EmailDraft(
            lead_id=lead.id,
            recipient_name=lead.full_name,
            recipient_email=lead.email,
            company=lead.company,
            subject=f"{lead.company} EKS guardrails",
            body=f"Hi {lead.full_name}, noticed {lead.recent_signal}. KubeGuard prevents spikes.",
            cited_survival_signal=lead.recent_signal,
            email_evidence_phrase=f"noticed {lead.recent_signal}",
            matched_product_chunk="Predicts AWS EKS cost spikes 48h early.",
            personalization_score=95,
        )
        emails[lead.id] = draft
        await callbacks.on_email(draft)

    return PipelineFinalResult(
        run_id=run_id,
        market_audit=audit,
        icps=icps,
        verdicts=verdicts,
        emails=emails,
    )


async def _mock_resurrect_runner(
    run_id: str,
    lead: LeadRecord,
    old_verdict: SlayerVerdict,
    icp: ICPProfile,
) -> tuple[SlayerVerdict, EmailDraft]:
    new_verdict = old_verdict.model_copy(
        update={
            "survived": True,
            "resurrected_by_user": True,
            "headline_tag": "RESURRECTED: Founder Override",
        }
    )
    draft = EmailDraft(
        lead_id=lead.id,
        recipient_name=lead.full_name,
        recipient_email=lead.email,
        company=lead.company,
        subject=f"Quick idea for {lead.company}",
        body=f"Hi {lead.full_name}, saw {lead.recent_signal}. Happy to share benchmarks.",
        cited_survival_signal=lead.recent_signal,
        email_evidence_phrase=f"saw {lead.recent_signal}",
        matched_product_chunk="Auto-tunes HPA policies.",
        personalization_score=88,
    )
    return new_verdict, draft


async def test_event_bus_last_event_id_replay() -> None:
    bus = EventStreamBus("run_replay")
    for i in range(1, 16):
        await bus.publish(StreamEventType.AGENT_LOG, {"message": f"msg {i}"})
    await bus.close()

    replayed = [ev async for ev in bus.subscribe(last_event_id=10)]
    assert [ev.event_id for ev in replayed] == [11, 12, 13, 14, 15]


async def test_pacer_flushes_all_50_verdicts_before_completion() -> None:
    bus = EventStreamBus("run_pace")
    pacer = DualLanePacer(bus, normal_delay_s=0.002, fast_delay_s=0.001, backlog_threshold=25)
    pacer.start()
    telemetry = TelemetryAggregator(total_leads=50)

    for i in range(50):
        verdict = SlayerVerdict(
            lead_id=f"lead_{i+1:02d}",
            survived=(i < 8),
            rejection_category=None if i < 8 else RejectionCategory.TOO_SMALL,
            headline_tag="SURVIVED" if i < 8 else "KILLED: Too Small",
            reasoning="Test",
            icp_similarity_score=0.7,
            anti_icp_similarity_score=0.2,
            structural_match_score=0.7,
            qualification_score=80 if i < 8 else 20,
            confidence=0.9,
            slaying_level_applied=load_default_startup().slaying_level,
            latency_ms=50,
        )
        telemetry.record_verdict(verdict)
        await pacer.enqueue_verdict(verdict, telemetry.snapshot())

    await pacer.flush()
    await pacer.emit_immediate(StreamEventType.PIPELINE_COMPLETED, {"phase": "READY"})
    await pacer.stop()
    await bus.close()

    events = bus.history
    assert len(events) == 51
    assert all(ev.event_type == StreamEventType.LEAD_VERDICT for ev in events[:50])
    assert events[-1].event_type == StreamEventType.PIPELINE_COMPLETED


async def test_full_pipeline_stream_resurrect_dispatch_export() -> None:
    manager = RunManager(
        pipeline_runner=_mock_pipeline_runner,
        resurrect_runner=_mock_resurrect_runner,
        pacer_normal_delay_s=0.001,
        pacer_fast_delay_s=0.001,
    )
    test_app = FastAPI()
    test_app.include_router(create_pipeline_router(manager))

    startup = load_default_startup()
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        start_res = await client.post("/api/pipeline/start", json=startup.model_dump(mode="json"))
        assert start_res.status_code == 202
        run_id = start_res.json()["run_id"]

        # Wait for background task to finish cleanly (50 * 0.001s < 0.2s)
        run_state = manager.get_run(run_id)
        assert run_state.task is not None
        await run_state.task

        # Verify /stream replays complete history cleanly even post-completion
        stream_res = await client.get(f"/api/pipeline/{run_id}/stream")
        assert stream_res.status_code == 200
        assert "event: audit_completed" in stream_res.text
        assert "event: hunter_report" in stream_res.text
        assert stream_res.text.count("event: lead_verdict") == 50
        assert stream_res.text.count("event: email_drafted") == 8
        assert "event: pipeline_completed" in stream_res.text

        # Verify /state snapshot
        state_res = await client.get(f"/api/pipeline/{run_id}/state")
        assert state_res.status_code == 200
        snap = state_res.json()
        assert snap["telemetry"]["killed_count"] == 42
        assert snap["telemetry"]["survived_count"] == 8

        # Verify Resurrect (#4) flips killed lead_09 -> survived & updates telemetry
        res_res = await client.post(f"/api/pipeline/{run_id}/resurrect/lead_09")
        assert res_res.status_code == 200
        res_data = res_res.json()
        assert res_data["verdict"]["survived"] is True
        assert res_data["verdict"]["resurrected_by_user"] is True
        assert res_data["telemetry"]["killed_count"] == 41
        assert res_data["telemetry"]["survived_count"] == 9

        # Verify Dispatch
        surv_ids = [f"lead_{i:02d}" for i in range(1, 10)]
        disp_res = await client.post(
            f"/api/pipeline/{run_id}/dispatch",
            json={"lead_ids": surv_ids},
        )
        assert disp_res.status_code == 200
        assert disp_res.json()["dispatched_count"] == 9

        # Verify CSV Export includes resurrected lead_09 and SENT status
        csv_res = await client.get(f"/api/pipeline/{run_id}/export?format=csv")
        assert csv_res.status_code == 200
        rows = list(csv.DictReader(io.StringIO(csv_res.text)))
        assert len(rows) == 9
        lead_09_row = next(r for r in rows if r["lead_id"] == "lead_09")
        assert lead_09_row["resurrected_by_user"] == "True"
        assert lead_09_row["dispatch_status"] == "SENT"

        # Verify JSON Kill Audit Export
        json_res = await client.get(f"/api/pipeline/{run_id}/export?format=json")
        assert json_res.status_code == 200
        audit_payload = json.loads(json_res.text)
        assert len(audit_payload["leads_audit"]) == 50


async def test_gemini_api_overload_emits_pipeline_error_and_closes_stream() -> None:
    async def _failing_runner(run_id, startup_input, leads, callbacks):
        await callbacks.on_phase(PipelinePhase.AUDITING)
        raise _FakeGeminiUnavailableError(
            "Gemini API limit reached or service is temporarily overloaded. Please wait a short while and try again.",
            status_code=429,
        )

    manager = RunManager(pipeline_runner=_failing_runner)
    startup = load_default_startup()
    state = await manager.start_run(startup)
    assert state.task is not None
    await state.task

    assert state.phase == PipelinePhase.ERROR
    assert state.bus.is_closed is True
    error_events = [
        ev for ev in state.bus.history if ev.event_type == StreamEventType.PIPELINE_ERROR
    ]
    assert len(error_events) == 1
    assert error_events[0].payload["status_code"] == 429
    assert "overloaded" in error_events[0].payload["message"]


async def test_run_manager_max_runs_and_ttl_eviction() -> None:
    manager = RunManager(
        max_runs=3,
        ttl_seconds=1,
        pipeline_runner=_mock_pipeline_runner,
        pacer_normal_delay_s=0.0,
        pacer_fast_delay_s=0.0,
    )
    startup = load_default_startup().model_copy(
        update={"leads": load_preset_leads()[:5]}
    )

    run_ids: list[str] = []
    for _ in range(4):
        st = await manager.start_run(startup)
        assert st.task is not None
        await st.task
        run_ids.append(st.run_id)

    # Max runs = 3, so oldest run_ids[0] was evicted
    assert len(manager._runs) == 3
    assert run_ids[0] not in manager._runs

    # Force TTL expiration on remaining runs
    for st in manager._runs.values():
        st.created_at = time.time() - 10
    st_new = await manager.start_run(startup)
    assert st_new.task is not None
    await st_new.task
    assert len(manager._runs) == 1
    assert st_new.run_id in manager._runs
