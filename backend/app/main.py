from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import DATA_DIR, settings
from app.models.schemas import HealthResponse, ParseCsvResponse, PresetResponse
from app.routers.pipeline_router import pipeline_router
from app.services.lead_loader import (
    load_default_startup,
    load_preset_leads,
    parse_leads_csv_bytes,
)

app = FastAPI(
    title="LeadSlayer AI API",
    version="0.1.0",
    description="Autonomous GTM Engine (Google ADK 2.0 + FastAPI)",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline_router)


@app.get("/api/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    preset_ok = (DATA_DIR / "default_startup.json").exists() and (
        DATA_DIR / "leads_50.json"
    ).exists()
    return HealthResponse(
        status="ok",
        models={
            "brain": settings.gemini_brain_model,
            "workhorse": settings.gemini_workhorse_model,
            "embedding": settings.gemini_embedding_model,
        },
        default_demo_ready=preset_ok,
    )


@app.get("/api/demo/preset", response_model=PresetResponse)
def get_demo_preset() -> PresetResponse:
    try:
        startup = load_default_startup()
        leads = load_preset_leads()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=f"Missing preset data file: {exc}") from exc
    return PresetResponse(startup=startup, leads=leads)


@app.post("/api/leads/parse-csv", response_model=ParseCsvResponse)
async def parse_csv_leads(file: UploadFile = File(...)) -> ParseCsvResponse:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a valid .csv file.")
    raw_bytes = await file.read()
    try:
        leads, warnings = parse_leads_csv_bytes(raw_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ParseCsvResponse(count=len(leads), leads=leads, warnings=warnings)
