from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import numpy as np
import pytest
from mcp import ClientSession
from mcp.client.stdio import stdio_client

from app import mcp_server
from app.agents.pipeline import maybe_recover_zero_survivors
from app.main import app
from app.memory.vector_store import HybridMatchContext
from app.models.schemas import (
    ICPProfile,
    MarketAuditResult,
    RejectionCategory,
    SlayerVerdict,
    SlayingLevel,
)
from app.services import mail_account
from app.services.lead_loader import load_default_startup, load_preset_leads
from app.services.mcp_client import build_adk_mcp_toolset, build_mcp_server_params, inspect_mcp_server


class _RecoveryCallbacks:
    def __init__(self) -> None:
        self.logs: list[str] = []
        self.verdicts: list[SlayerVerdict] = []
        self.models: list[str] = []

    async def on_phase(self, phase) -> None:
        pass

    async def on_log(self, message: str) -> None:
        self.logs.append(message)

    async def on_model_call(self, model_id) -> None:
        self.models.append(model_id.value)

    async def on_audit(self, audit) -> None:
        pass

    async def on_icps(self, icps) -> None:
        pass

    async def on_leads_loaded(self, leads) -> None:
        pass

    async def on_hunter_report(self, report) -> None:
        pass

    async def on_verdict(self, verdict: SlayerVerdict) -> None:
        self.verdicts.append(verdict)

    async def on_email(self, draft) -> None:
        pass

    async def on_mcp_tool_call(self, record) -> None:
        pass


async def test_mcp_server_stdio_handshake_and_tools() -> None:
    status = await inspect_mcp_server()
    assert status.connected is True
    assert status.server_name == "leadslayer-ops-mcp"
    assert set(status.tools) == {
        "check_and_update_dnc_crm",
        "schedule_followup_reminder",
        "stage_or_dispatch_email_mcp",
        "save_campaign_artifacts",
        "run_leadslayer_campaign",
        "dispatch_campaign_emails",
    }


async def test_mcp_server_tools_end_to_end_isolated(tmp_path: Path, monkeypatch) -> None:
    crm_file = tmp_path / "crm_dnc.json"
    exports_dir = tmp_path / "exports"
    monkeypatch.setattr(mcp_server, "CRM_DNC_FILE", crm_file)
    monkeypatch.setattr(mcp_server, "EXPORTS_DIR", exports_dir)
    # Also redirect _load_crm_store / _save_crm_store defaults via wrapper
    orig_load = mcp_server._load_crm_store
    orig_save = mcp_server._save_crm_store
    monkeypatch.setattr(mcp_server, "_load_crm_store", lambda crm_path=crm_file: orig_load(crm_file))
    monkeypatch.setattr(mcp_server, "_save_crm_store", lambda data, crm_path=crm_file: orig_save(data, crm_file))

    # 1. Clear domain check -> allowed
    clear_res = json.loads(
        mcp_server.check_and_update_dnc_crm(
            domain="https://www.velvetbloom.co/about",
            company="Velvet Bloom",
            action="check",
        )
    )
    assert clear_res["domain"] == "velvetbloom.co"
    assert clear_res["allowed"] is True

    # 2. Mark competitor as DNC -> blocked in stage_or_dispatch_email_mcp
    dnc_res = json.loads(
        mcp_server.check_and_update_dnc_crm(
            domain="competitor.example",
            company="Competitor Inc",
            action="mark_dnc",
            reason="Direct competitor",
        )
    )
    assert dnc_res["allowed"] is False
    assert dnc_res["crm_status"] == "DNC"

    blocked_dispatch = json.loads(
        await mcp_server.stage_or_dispatch_email_mcp(
            lead_id="l_blocked",
            recipient_email="exec@competitor.example",
            recipient_name="Bob",
            company="Competitor Inc",
            subject="hello",
            body="Testing DNC gate.",
            delivery_mode="SANDBOX",
        )
    )
    assert blocked_dispatch["status"] == "BLOCKED"

    # 3. Schedule follow-up reminder creates .json and RFC-5545 .ics
    rem = json.loads(
        mcp_server.schedule_followup_reminder(
            run_id="test_run_1",
            lead_id="orb_01",
            company="Velvet Bloom",
            contact_name="Elena Vance",
            priority="HIGH",
            due_in_days=2,
            reason="Q4 gift set launch",
        )
    )
    assert rem["scheduled"] is True
    assert Path(rem["ics_path"]).is_file()
    assert "BEGIN:VCALENDAR" in Path(rem["ics_path"]).read_text(encoding="utf-8")

    # 4. Save campaign artifacts writes executive_brief.md + CSV + JSON
    art = json.loads(
        mcp_server.save_campaign_artifacts(
            run_id="test_run_1",
            product_name="Orbix Packaging",
            summary_markdown="## Ready for launch",
            survivors_csv="lead_id,company\norb_01,Velvet Bloom\n",
            kill_audit_json='{"killed": 10}',
        )
    )
    assert Path(art["files"]["executive_brief"]).is_file()
    assert Path(art["files"]["survivors_csv"]).is_file()
    assert Path(art["files"]["kill_audit_json"]).is_file()


async def test_adk_mcp_toolset_discovers_tools_and_closes() -> None:
    toolset = build_adk_mcp_toolset(timeout=15.0)
    try:
        tools = await toolset.get_tools()
        names = {t.name for t in tools}
        assert "check_and_update_dnc_crm" in names
        assert "save_campaign_artifacts" in names
        assert "schedule_followup_reminder" in names
        assert "stage_or_dispatch_email_mcp" in names
    finally:
        await toolset.close()


async def test_zero_survivor_recovery_relaxes_ruthless_to_normal() -> None:
    startup = load_default_startup().model_copy(update={"slaying_level": SlayingLevel.RUTHLESS})
    leads = load_preset_leads()[:2]
    audit = MarketAuditResult(
        market_reality_summary="Real buyers need urgent cost control.",
        founder_blind_spots=["Broad assumption"],
        sharpened_value_prop="EKS spike prevention.",
        anti_icp_red_flags=["<20 employees"],
        market_readiness_score=80,
    )
    icp = ICPProfile(
        id="icp_1",
        name="Series A EKS",
        target_roles=["CTO"],
        min_employees=20,
        max_employees=300,
        required_tech_signals=["AWS"],
        buying_triggers=["Bill spike"],
        instant_disqualifiers=["Freeze"],
        vector_doc_id="icp_1",
    )
    priors = {
        lead.id: HybridMatchContext(
            lead_id=lead.id,
            best_icp=icp,
            icp_similarity_score=0.75,
            anti_icp_similarity_score=0.15,
            structural_match_score=0.80,
            prior_score_100=72,
            matched_anti_icp_rule="",
            query_vector=np.zeros(8, dtype=np.float32),
        )
        for lead in leads
    }
    killed_verdicts = {
        lead.id: SlayerVerdict(
            lead_id=lead.id,
            survived=False,
            rejection_category=RejectionCategory.NO_URGENCY_SIGNAL,
            headline_tag="KILLED: Soft Urgency",
            reasoning="Needs relaxed tactical check.",
            icp_similarity_score=0.75,
            anti_icp_similarity_score=0.15,
            structural_match_score=0.80,
            qualification_score=45,
            confidence=0.8,
            slaying_level_applied=SlayingLevel.RUTHLESS,
            latency_ms=40,
        )
        for lead in leads
    }

    class _FakeRecoverySlayer:
        @property
        def aio(self):
            return self

        @property
        def models(self):
            return self

        async def generate_content(self, *, model: str, contents: str, config=None):
            return SimpleNamespace(
                text=json.dumps(
                    {
                        "verdicts": [
                            {
                                "lead_id": leads[0].id,
                                "disqualifier_signals_found": [],
                                "tier_triggered": "NONE",
                                "rejection_category": None,
                                "reasoning": "Strong Series A EKS fit recovered at NORMAL.",
                                "survived": True,
                                "headline_tag": "SURVIVED: Tactical Fit",
                                "confidence": 0.85,
                            },
                            {
                                "lead_id": leads[1].id,
                                "disqualifier_signals_found": ["Weak urgency"],
                                "tier_triggered": "TIER_3_FRICTION",
                                "rejection_category": "NO_URGENCY_SIGNAL",
                                "reasoning": "Still lacks immediate trigger.",
                                "survived": False,
                                "headline_tag": "KILLED: No Trigger",
                                "confidence": 0.82,
                            },
                        ]
                    }
                )
            )

    cb = _RecoveryCallbacks()
    updated_startup, updated_verdicts = await maybe_recover_zero_survivors(
        startup,
        audit,
        leads,
        priors,
        killed_verdicts,
        cb,
        client=_FakeRecoverySlayer(),
    )
    assert updated_startup.slaying_level == SlayingLevel.NORMAL
    assert updated_verdicts[leads[0].id].survived is True
    assert any("RecoveryCoordinator" in log for log in cb.logs)


async def test_native_mail_connect_status_and_no_harvey_leaks(monkeypatch) -> None:
    mail_account.mail_account_store.disconnect()

    async def _fake_verify(**kwargs):
        return None

    from app.routers import mail_router as mr

    monkeypatch.setattr(mr, "verify_smtp_credentials", _fake_verify)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        connect_res = await client.post(
            "/api/mail/connect-smtp",
            json={
                "email": "founder@orbixpackaging.com",
                "password": "app-password-1234",
                "smtp_host": "smtp.gmail.com",
                "smtp_port": 587,
                "sender_name": "Orbix GTM",
                "postal_address": "100 Box Way, Austin TX",
                "verify_connection": True,
            },
        )
        assert connect_res.status_code == 200
        body = connect_res.json()
        assert body["smtp_configured"] is True
        assert body["active_provider"] == "SMTP"
        assert "app-password-1234" not in json.dumps(body)
        assert "harvey" not in json.dumps(body).lower()

        status_res = await client.get("/api/pipeline/mail-status")
        assert status_res.status_code == 200
        assert status_res.json()["smtp_configured"] is True

        disc_res = await client.post("/api/mail/disconnect")
        assert disc_res.status_code == 200
        assert disc_res.json()["smtp_configured"] is False


async def test_mcp_campaign_and_selective_dispatch_simulation_fallback(tmp_path: Path, monkeypatch) -> None:
    crm_file = tmp_path / "crm_dnc.json"
    exports_dir = tmp_path / "exports"
    monkeypatch.setattr(mcp_server, "CRM_DNC_FILE", crm_file)
    monkeypatch.setattr(mcp_server, "EXPORTS_DIR", exports_dir)
    orig_load = mcp_server._load_crm_store
    orig_save = mcp_server._save_crm_store
    monkeypatch.setattr(mcp_server, "_load_crm_store", lambda crm_path=crm_file: orig_load(crm_file))
    monkeypatch.setattr(mcp_server, "_save_crm_store", lambda data, crm_path=crm_file: orig_save(data, crm_file))
    mail_account.mail_account_store.disconnect()

    camp_res = json.loads(
        await mcp_server.run_leadslayer_campaign(
            product_name="KubeGuard AI",
            description="Autonomous Kubernetes FinOps guardrail for AWS EKS teams.",
            founder_assumptions="Any startup on AWS needs FinOps.",
            target_qualified_leads=5,
            execution_mode="SAFE_REPLAY",
        )
    )
    assert camp_res["survivor_count"] == 5
    assert [item["index"] for item in camp_res["numbered_survivors"]] == [1, 2, 3, 4, 5]
    assert camp_res["mailbox_attached"] is False

    # User selects numbers "1, 3" -> no mailbox attached -> verified Sandbox simulation
    disp_res = json.loads(
        await mcp_server.dispatch_campaign_emails(
            run_id=camp_res["run_id"],
            selection="1, 3",
            delivery_mode="AUTO",
        )
    )
    assert disp_res["mode_executed"] == "SANDBOX_SIMULATION"
    assert disp_res["dispatched_count"] == 2
    assert len(disp_res["selected_lead_ids"]) == 2
    assert disp_res["selected_lead_ids"][0] == camp_res["numbered_survivors"][0]["lead_id"]
    assert disp_res["selected_lead_ids"][1] == camp_res["numbered_survivors"][2]["lead_id"]
    assert Path(disp_res["receipts_file"]).is_file()
    assert (exports_dir / camp_res["run_id"] / "executive_brief.md").is_file()
    verified_csv = exports_dir / camp_res["run_id"] / "verified_leads.csv"
    assert verified_csv.is_file()
    assert disp_res["verified_leads_csv"] == str(verified_csv)

    import csv
    import io
    from app.routers import pipeline_router as pr_mod

    monkeypatch.setattr(pr_mod, "EXPORTS_DIR", exports_dir)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        list_res = await client.get("/api/pipeline/exports")
        assert list_res.status_code == 200
        items = list_res.json()
        assert any(it["run_id"] == camp_res["run_id"] and it["verified_count"] >= 5 for it in items)

        dl_res = await client.get(f"/api/pipeline/{camp_res['run_id']}/export?format=csv")
        assert dl_res.status_code == 200
        assert "text/csv" in dl_res.headers["content-type"]
        rows = list(csv.DictReader(io.StringIO(dl_res.text)))
        assert len(rows) >= 5
        assert {"domain", "email_status", "mx_provider", "source_channel"}.issubset(rows[0].keys())
        dispatched_rows = [r for r in rows if r["lead_id"] in disp_res["selected_lead_ids"]]
        assert all(r["dispatch_status"] == "SENT" for r in dispatched_rows)
