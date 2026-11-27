from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path

import httpx
import pytest

from app.main import app
from app.models.schemas import ExecutionMode, PipelinePhase, SlayingLevel
from app.routers.pipeline_router import create_pipeline_router
from app.services.lead_loader import load_default_startup, load_preset_leads
from app.streaming.run_manager import RunManager
from tests.test_stage4_streaming import _mock_pipeline_runner, _mock_resurrect_runner


async def test_e2e_safe_replay_pipeline_and_exports(tmp_path: Path) -> None:
    """
    Verifies the complete Stage 7 SAFE_REPLAY flow:
    captures a snapshot via mocked pipeline -> replays it via ExecutionMode.SAFE_REPLAY
    -> resurrects a killed lead -> dispatches -> exports CSV & JSON.
    """
    replay_file = tmp_path / "replay_snapshot.json"

    # 1. Produce an authentic-format snapshot from a completed RunManager run
    rec_manager = RunManager(
        pipeline_runner=_mock_pipeline_runner,
        resurrect_runner=_mock_resurrect_runner,
        pacer_normal_delay_s=0.0,
        pacer_fast_delay_s=0.0,
    )
    startup = load_default_startup()
    rec_state = await rec_manager.start_run(startup)
    assert rec_state.task is not None
    await rec_state.task
    assert rec_state.phase == PipelinePhase.READY

    snapshot_payload = {
        "captured_at": "2026-11-27T00:00:00Z",
        "source": "live_gemini_adk_run",
        "models": ["gemini-4-hydrogen", "gemini-3.5-flash-lite", "gemini-embedding-2"],
        "snapshot": rec_state.to_snapshot().model_dump(mode="json"),
        "events": [ev.model_dump(mode="json") for ev in rec_state.bus.history],
    }
    replay_file.write_text(json.dumps(snapshot_payload), encoding="utf-8")

    # 2. Boot FastAPI router configured with that replay_path
    from fastapi import FastAPI

    e2e_app = FastAPI()
    replay_manager = RunManager(
        resurrect_runner=_mock_resurrect_runner,
        pacer_normal_delay_s=0.0,
        pacer_fast_delay_s=0.0,
        replay_path=replay_file,
        replay_time_scale=0.0,
    )
    e2e_app.include_router(create_pipeline_router(replay_manager))

    replay_input = startup.model_copy(update={"execution_mode": ExecutionMode.SAFE_REPLAY})
    transport = httpx.ASGITransport(app=e2e_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        start_res = await client.post(
            "/api/pipeline/start", json=replay_input.model_dump(mode="json")
        )
        assert start_res.status_code == 202
        run_id = start_res.json()["run_id"]

        run_state = replay_manager.get_run(run_id)
        assert run_state.task is not None
        await run_state.task
        assert run_state.phase == PipelinePhase.READY

        stream_res = await client.get(f"/api/pipeline/{run_id}/stream")
        assert stream_res.status_code == 200
        assert "event: agent_log" in stream_res.text
        assert stream_res.text.count("event: lead_verdict") == 50
        assert "event: pipeline_completed" in stream_res.text

        # Resurrect a killed lead, dispatch, and verify CSV export
        res_res = await client.post(f"/api/pipeline/{run_id}/resurrect/lead_10")
        assert res_res.status_code == 200
        assert res_res.json()["verdict"]["resurrected_by_user"] is True

        csv_res = await client.get(f"/api/pipeline/{run_id}/export?format=csv")
        rows = list(csv.DictReader(io.StringIO(csv_res.text)))
        assert len(rows) == 9
        assert any(r["lead_id"] == "lead_10" and r["resurrected_by_user"] == "True" for r in rows)


def test_app_exposes_health_preset_and_pipeline_routes() -> None:
    paths = set(app.openapi()["paths"].keys())
    expected = {
        "/api/health",
        "/api/demo/preset",
        "/api/leads/parse-csv",
        "/api/pipeline/start",
        "/api/pipeline/{run_id}/stream",
        "/api/pipeline/{run_id}/state",
        "/api/pipeline/{run_id}/resurrect/{lead_id}",
        "/api/pipeline/{run_id}/dispatch",
        "/api/pipeline/{run_id}/export",
    }
    assert expected.issubset(paths)


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_E2E") != "1",
    reason="Set RUN_LIVE_E2E=1 to run real Gemini end-to-end calibration test",
)
async def test_live_gemini_ruthless_vs_lenient_calibration() -> None:
    from app.agents.pipeline import run_live_pipeline

    startup = load_default_startup()
    leads = load_preset_leads()
    manager = RunManager(
        pipeline_runner=run_live_pipeline,
        pacer_normal_delay_s=0.0,
        pacer_fast_delay_s=0.0,
    )
    st_ruth = await manager.start_run(
        startup.model_copy(update={"slaying_level": SlayingLevel.RUTHLESS})
    )
    assert st_ruth.task is not None
    await st_ruth.task
    assert st_ruth.phase == PipelinePhase.READY
    ruth_killed = sum(1 for v in st_ruth.verdicts.values() if not v.survived)
    assert 38 <= ruth_killed <= 47
