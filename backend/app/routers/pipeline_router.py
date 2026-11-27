from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response
from sse_starlette.sse import EventSourceResponse

from app.harvey_bridge.dispatcher import get_harvey_status
from app.models.schemas import (
    DispatchRequest,
    DispatchResponse,
    HarveyStatusResponse,
    PipelineStartResponse,
    ResurrectResponse,
    RunStateSnapshot,
    StartupInput,
)
from app.streaming.exporter import build_kill_audit_json, build_survivors_csv
from app.streaming.run_manager import (
    LeadNotFoundError,
    RunManager,
    RunNotFoundError,
    run_manager as default_run_manager,
)


def create_pipeline_router(manager: RunManager = default_run_manager) -> APIRouter:
    router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

    @router.get("/harvey-status", response_model=HarveyStatusResponse)
    async def harvey_status() -> HarveyStatusResponse:
        return get_harvey_status()

    @router.post("/start", status_code=202, response_model=PipelineStartResponse)
    async def start_pipeline(startup_input: StartupInput) -> PipelineStartResponse:
        state = await manager.start_run(startup_input)
        return PipelineStartResponse(
            run_id=state.run_id,
            stream_url=f"/api/pipeline/{state.run_id}/stream",
        )

    @router.get("/{run_id}/stream")
    async def stream_pipeline(
        run_id: str,
        request: Request,
        last_event_id: int | None = Query(default=None, ge=0),
    ) -> EventSourceResponse:
        try:
            state = manager.get_run(run_id)
        except RunNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        header_last_id = request.headers.get("last-event-id")
        resolved_last_id = last_event_id
        if resolved_last_id is None and header_last_id and header_last_id.isdigit():
            resolved_last_id = int(header_last_id)

        async def event_generator():
            async for ev in state.bus.subscribe(last_event_id=resolved_last_id):
                if await request.is_disconnected():
                    break
                yield {
                    "id": str(ev.event_id),
                    "event": ev.event_type.value,
                    "data": ev.model_dump_json(),
                }

        return EventSourceResponse(
            event_generator(),
            ping=15,
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @router.get("/{run_id}/state", response_model=RunStateSnapshot)
    async def get_pipeline_state(run_id: str) -> RunStateSnapshot:
        try:
            state = manager.get_run(run_id)
        except RunNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return state.to_snapshot()

    @router.post("/{run_id}/resurrect/{lead_id}", response_model=ResurrectResponse)
    async def resurrect_lead(run_id: str, lead_id: str) -> ResurrectResponse:
        try:
            return await manager.resurrect_lead(run_id, lead_id)
        except (RunNotFoundError, LeadNotFoundError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            user_msg = getattr(exc, "user_message", None) or str(exc)
            status_code = getattr(exc, "status_code", None) or 503
            raise HTTPException(status_code=status_code, detail=user_msg) from exc

    @router.post("/{run_id}/dispatch", response_model=DispatchResponse)
    async def dispatch_emails(
        run_id: str, payload: DispatchRequest
    ) -> DispatchResponse:
        try:
            return await manager.dispatch_emails(
                run_id, payload.lead_ids, delivery_mode=payload.delivery_mode
            )
        except RunNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/{run_id}/export")
    async def export_run_report(
        run_id: str,
        format: Literal["csv", "json"] = Query(default="csv"),
    ) -> Response:
        try:
            state = manager.get_run(run_id)
        except RunNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        if format == "csv":
            csv_body = build_survivors_csv(state)
            return Response(
                content=csv_body,
                media_type="text/csv; charset=utf-8",
                headers={
                    "Content-Disposition": f'attachment; filename="leadslayer_{run_id}_survivors.csv"'
                },
            )

        audit_json = build_kill_audit_json(state)
        return Response(
            content=json.dumps(audit_json, indent=2),
            media_type="application/json; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="leadslayer_{run_id}_kill_audit.json"'
            },
        )

    return router


pipeline_router = create_pipeline_router()
