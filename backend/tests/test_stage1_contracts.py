from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from app.config import CONTRACTS_DIR, DATA_DIR
from app.main import app
from app.models.schemas import LeadRecord, SlayerVerdict, SlayingLevel
from app.services.lead_loader import (
    load_default_startup,
    load_preset_leads,
    parse_leads_csv_bytes,
)

client = TestClient(app)


def test_50_leads_dataset_integrity() -> None:
    startup = load_default_startup()
    assert startup.product_name == "KubeGuard AI"
    assert startup.slaying_level == SlayingLevel.RUTHLESS

    leads = load_preset_leads()
    assert len(leads) == 50

    ids = [lead.id for lead in leads]
    emails = [lead.email.lower() for lead in leads]
    companies = [lead.company.lower() for lead in leads]

    assert len(set(ids)) == 50
    assert len(set(emails)) == 50
    assert len(set(companies)) == 50
    assert all(isinstance(lead, LeadRecord) for lead in leads)


def test_csv_roundtrip_matches_json_exactly() -> None:
    json_leads = load_preset_leads()
    csv_bytes = (DATA_DIR / "leads_50.csv").read_bytes()
    csv_leads, warnings = parse_leads_csv_bytes(csv_bytes)

    assert warnings == []
    assert len(csv_leads) == 50
    assert [l.model_dump() for l in csv_leads] == [l.model_dump() for l in json_leads]


def test_messy_csv_header_aliases() -> None:
    sample_csv = (
        "Name,Title,Company Name,Employee Count,Tech Stack,News,Work Email\n"
        "Alex Rivera,CTO,CloudNova,85,\"AWS, EKS, Kubernetes\",AWS bill spiked 2x,alex@cloudnova.io\n"
    ).encode("utf-8")
    leads, warnings = parse_leads_csv_bytes(sample_csv)
    assert warnings == []
    assert len(leads) == 1
    assert leads[0].full_name == "Alex Rivera"
    assert leads[0].role == "CTO"
    assert leads[0].company == "CloudNova"
    assert leads[0].employee_count == 85
    assert leads[0].tech_stack == ["AWS", "EKS", "Kubernetes"]
    assert leads[0].email == "alex@cloudnova.io"


def test_slayer_verdict_requires_rejection_category_when_killed() -> None:
    with pytest.raises(ValueError, match="rejection_category"):
        SlayerVerdict(
            lead_id="lead_01",
            survived=False,
            rejection_category=None,
            headline_tag="KILLED: Missing Reason",
            reasoning="Test",
            icp_similarity_score=0.5,
            anti_icp_similarity_score=0.5,
            structural_match_score=0.5,
            qualification_score=20,
            confidence=0.9,
            slaying_level_applied=SlayingLevel.RUTHLESS,
            latency_ms=100,
        )


def test_stage1_api_endpoints_and_latency() -> None:
    health_res = client.get("/api/health")
    assert health_res.status_code == 200
    health_data = health_res.json()
    assert health_data["status"] == "ok"
    assert health_data["default_demo_ready"] is True
    assert health_data["models"]["brain"] == "gemini-4-hydrogen"
    assert health_data["models"]["workhorse"] == "gemini-3.5-flash-lite"
    assert health_data["models"]["embedding"] == "gemini-embedding-2"

    start = time.perf_counter()
    preset_res = client.get("/api/demo/preset")
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert preset_res.status_code == 200
    assert elapsed_ms < 50  # Fast local response
    preset_data = preset_res.json()
    assert len(preset_data["leads"]) == 50

    csv_bytes = (DATA_DIR / "leads_50.csv").read_bytes()
    upload_res = client.post(
        "/api/leads/parse-csv",
        files={"file": ("leads_50.csv", csv_bytes, "text/csv")},
    )
    assert upload_res.status_code == 200
    assert upload_res.json()["count"] == 50


def test_exported_schema_spec_exists() -> None:
    spec_path = CONTRACTS_DIR / "schema_spec.json"
    assert spec_path.exists()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    for key in (
        "StartupInput",
        "MarketAuditResult",
        "HunterReport",
        "LeadRecord",
        "SlayerVerdict",
        "EmailDraft",
        "StreamEvent",
    ):
        assert key in spec["schemas"]


def test_url_fetcher_safety_and_html_extraction() -> None:
    from app.services.url_fetcher import extract_readable_text, is_safe_public_url

    assert is_safe_public_url("http://127.0.0.1:8000") is None
    assert is_safe_public_url("http://localhost/admin") is None
    assert is_safe_public_url("http://192.168.1.10") is None
    assert is_safe_public_url("kubeguard.ai") == "https://kubeguard.ai"

    sample_html = """
    <html>
      <head>
        <title>KubeGuard AI — Autonomous FinOps</title>
        <meta name="description" content="Cut AWS EKS waste by 40% automatically." />
        <script>console.log("ignore me");</script>
      </head>
      <body><h1>Predictive Kubernetes Guardrails</h1><p>Zero code changes.</p></body>
    </html>
    """
    extracted = extract_readable_text(sample_html)
    assert "KubeGuard AI" in extracted
    assert "Cut AWS EKS waste" in extracted
    assert "Predictive Kubernetes Guardrails" in extracted
    assert "ignore me" not in extracted
