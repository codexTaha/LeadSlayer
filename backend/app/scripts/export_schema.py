from __future__ import annotations

import json
from pathlib import Path
from pydantic import TypeAdapter

from app.config import CONTRACTS_DIR
from app.models.schemas import (
    DispatchRequest,
    DispatchResponse,
    EmailDraft,
    HealthResponse,
    ICPProfile,
    LeadRecord,
    MarketAuditResult,
    ParseCsvResponse,
    PipelineStartResponse,
    PresetResponse,
    ResurrectResponse,
    RunStateSnapshot,
    SlayerVerdict,
    StartupInput,
    StreamEvent,
    TelemetryMetrics,
)


def export_all_schemas(output_dir: Path = CONTRACTS_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    models = {
        "StartupInput": StartupInput,
        "MarketAuditResult": MarketAuditResult,
        "ICPProfile": ICPProfile,
        "LeadRecord": LeadRecord,
        "SlayerVerdict": SlayerVerdict,
        "EmailDraft": EmailDraft,
        "TelemetryMetrics": TelemetryMetrics,
        "StreamEvent": StreamEvent,
        "RunStateSnapshot": RunStateSnapshot,
        "HealthResponse": HealthResponse,
        "PresetResponse": PresetResponse,
        "ParseCsvResponse": ParseCsvResponse,
        "PipelineStartResponse": PipelineStartResponse,
        "ResurrectResponse": ResurrectResponse,
        "DispatchRequest": DispatchRequest,
        "DispatchResponse": DispatchResponse,
    }
    bundle = {
        "title": "LeadSlayer AI Shared Data Contracts",
        "version": "1.0.0",
        "schemas": {name: TypeAdapter(model).json_schema() for name, model in models.items()},
    }
    target = output_dir / "schema_spec.json"
    target.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    return target


if __name__ == "__main__":
    out_path = export_all_schemas()
    print(f"Exported shared contracts schema to {out_path}")
