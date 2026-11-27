from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response
from sse_starlette.sse import EventSourceResponse

from app.config import EXPORTS_DIR
from app.harvey_bridge.dispatcher import get_mail_status
from app.models.schemas import (
    DispatchRequest,
    DispatchResponse,
    EmailDraft,
    LeadRecord,
    MailStatusResponse,
    MCPStatusResponse,
    PipelineStartResponse,
    ResurrectResponse,
    RunStateSnapshot,
    SlayerVerdict,
    StartupInput,
)
from app.services.mcp_client import inspect_mcp_server
from app.streaming.exporter import (
    build_kill_audit_json,
    build_survivors_csv,
    build_verified_leads_csv,
)
from app.streaming.run_manager import (
    LeadNotFoundError,
    RunManager,
    RunNotFoundError,
    run_manager as default_run_manager,
)


def _safe_run_slug(run_id: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in run_id).strip("_") or "run"


def _read_disk_export_csv(run_dir: Path) -> str | None:
    for fname in ("verified_leads.csv", "survivors.csv"):
        candidate = run_dir / fname
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    state_file = run_dir / "run_state.json"
    if state_file.is_file():
        raw = json.loads(state_file.read_text(encoding="utf-8"))
        leads = [LeadRecord.model_validate(l) for l in raw.get("leads", {}).values()]
        verdicts = {lid: SlayerVerdict.model_validate(v) for lid, v in raw.get("verdicts", {}).items()}
        emails = {lid: EmailDraft.model_validate(d) for lid, d in raw.get("emails", {}).items()}
        return build_verified_leads_csv(leads, verdicts, emails)
    return None


def _list_saved_exports(exports_dir: Path = EXPORTS_DIR) -> list[dict[str, Any]]:
    if not exports_dir.is_dir():
        return []
    entries: list[tuple[float, dict[str, Any]]] = []
    for run_dir in exports_dir.iterdir():
        if not run_dir.is_dir():
            continue
        csv_file = next(
            (run_dir / name for name in ("verified_leads.csv", "survivors.csv") if (run_dir / name).is_file()),
            None,
        )
        state_file = run_dir / "run_state.json"
        if csv_file is None and not state_file.is_file():
            continue
        product_name = "LeadSlayer Run"
        verified_count = 0
        if state_file.is_file():
            try:
                raw = json.loads(state_file.read_text(encoding="utf-8"))
                product_name = raw.get("product_name") or product_name
                verified_count = sum(
                    1 for v in raw.get("verdicts", {}).values() if v.get("survived")
                )
            except (OSError, json.JSONDecodeError):
                pass
        if verified_count == 0 and csv_file is not None:
            try:
                rows = list(csv.DictReader(io.StringIO(csv_file.read_text(encoding="utf-8"))))
                verified_count = len(rows)
            except OSError:
                pass
        stat_target = csv_file or state_file
        mtime = stat_target.stat().st_mtime
        entries.append(
            (
                mtime,
                {
                    "run_id": run_dir.name,
                    "product_name": product_name,
                    "verified_count": verified_count,
                    "updated_at_ms": int(mtime * 1000),
                    "csv_url": f"/api/pipeline/{run_dir.name}/export?format=csv",
                },
            )
        )
    entries.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in entries[:10]]


def create_pipeline_router(manager: RunManager = default_run_manager) -> APIRouter:
    router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

    @router.get("/mail-status", response_model=MailStatusResponse)
    async def mail_status() -> MailStatusResponse:
        return get_mail_status()

    @router.get("/harvey-status", response_model=MailStatusResponse, include_in_schema=False)
    async def legacy_mail_status() -> MailStatusResponse:
        return get_mail_status()

    @router.get("/mcp-status", response_model=MCPStatusResponse)
    async def mcp_status() -> MCPStatusResponse:
        return await inspect_mcp_server()

    @router.get("/exports")
    async def list_saved_exports() -> list[dict[str, Any]]:
        exports_dir = getattr(manager, "_exports_dir", None) or EXPORTS_DIR
        return _list_saved_exports(exports_dir)

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
        exports_dir = getattr(manager, "_exports_dir", None) or EXPORTS_DIR
        safe_run = _safe_run_slug(run_id)
        try:
            state = manager.get_run(run_id)
        except RunNotFoundError as exc:
            run_dir = exports_dir / safe_run
            if format == "csv":
                csv_body = _read_disk_export_csv(run_dir)
                if csv_body is not None:
                    return Response(
                        content=csv_body,
                        media_type="text/csv; charset=utf-8",
                        headers={
                            "Content-Disposition": f'attachment; filename="leadslayer_{safe_run}_verified_leads.csv"'
                        },
                    )
            else:
                for fname in ("kill_audit.json", "run_state.json"):
                    candidate = run_dir / fname
                    if candidate.is_file():
                        return Response(
                            content=candidate.read_text(encoding="utf-8"),
                            media_type="application/json; charset=utf-8",
                            headers={
                                "Content-Disposition": f'attachment; filename="leadslayer_{safe_run}_{fname}"'
                            },
                        )
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        if format == "csv":
            csv_body = build_survivors_csv(state)
            return Response(
                content=csv_body,
                media_type="text/csv; charset=utf-8",
                headers={
                    "Content-Disposition": f'attachment; filename="leadslayer_{safe_run}_verified_leads.csv"'
                },
            )

        audit_json = build_kill_audit_json(state)
        return Response(
            content=json.dumps(audit_json, indent=2),
            media_type="application/json; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="leadslayer_{safe_run}_kill_audit.json"'
            },
        )

    return router


pipeline_router = create_pipeline_router()
