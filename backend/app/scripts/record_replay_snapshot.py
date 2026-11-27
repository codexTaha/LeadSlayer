from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.pipeline import run_live_pipeline
from app.config import DATA_DIR
from app.models.schemas import ExecutionMode, PipelinePhase, SlayingLevel
from app.services.lead_loader import load_default_startup, load_preset_leads
from app.streaming.run_manager import RunManager


async def capture_authentic_replay(
    output_path: Path = DATA_DIR / "replay_snapshot.json",
) -> Path:
    """
    Runs the REAL live Google ADK 2.0 + Gemini pipeline once and saves the
    authentic captured output to data/replay_snapshot.json for emergency ?mode=replay.
    """
    startup = load_default_startup().model_copy(
        update={
            "slaying_level": SlayingLevel.RUTHLESS,
            "execution_mode": ExecutionMode.LIVE,
        }
    )
    leads = load_preset_leads()

    manager = RunManager(
        pipeline_runner=run_live_pipeline,
        pacer_normal_delay_s=0.0,
        pacer_fast_delay_s=0.0,
    )
    state = await manager.start_run(startup)
    assert state.task is not None
    await state.task

    if state.phase == PipelinePhase.ERROR:
        raise RuntimeError(f"Live capture failed: {state.error_message}")

    snapshot = state.to_snapshot()
    survived = sum(1 for v in snapshot.verdicts.values() if v.survived)
    assert len(snapshot.verdicts) == len(leads), "Expected all 50 verdicts"
    assert 3 <= survived <= 15, f"Unexpected survivor count during capture: {survived}"

    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source": "live_gemini_adk_run",
        "models": [
            "gemini-4-hydrogen",
            "gemini-3.5-flash-lite",
            "gemini-embedding-2",
        ],
        "snapshot": snapshot.model_dump(mode="json"),
        "events": [ev.model_dump(mode="json") for ev in state.bus.history],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp_path, output_path)
    print(
        f"Captured authentic Gemini replay snapshot -> {output_path} "
        f"({len(snapshot.verdicts)} verdicts, {survived} survivors, {len(snapshot.emails)} emails)"
    )
    return output_path


if __name__ == "__main__":
    asyncio.run(capture_authentic_replay())
