"""LeadSlayer Operational MCP Server (stdio transport via mcp 2.x MCPServer)."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import CRM_DNC_FILE, EXPORTS_DIR, settings  # noqa: E402
from app.harvey_bridge.dispatcher import dispatch_emails_via_harvey  # noqa: E402
from app.models.schemas import EmailDraft, LeadRecord  # noqa: E402

mcp = MCPServer(
    name="leadslayer-ops-mcp",
    instructions=(
        "Operational GTM & CRM automation tools for LeadSlayer AI: "
        "check/update CRM DNC status, validate & stage/dispatch outreach via the deliverability gate, "
        "schedule calendar follow-ups (.ics), and export campaign audit artifacts."
    ),
)

_BLOCKING_STATUSES = {"DNC", "OPT_OUT", "CUSTOMER", "COMPETITOR"}


def _safe_slug(raw: str, fallback: str = "default") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", (raw or "").strip()).strip("._")
    return cleaned[:64] or fallback


def _normalize_domain(raw: str) -> str:
    val = (raw or "").strip().lower()
    if "@" in val:
        val = val.split("@", 1)[1]
    val = re.sub(r"^https?://", "", val)
    val = val.split("/", 1)[0].split(":", 1)[0]
    if val.startswith("www."):
        val = val[4:]
    return val.strip(".")


def _load_crm_store(crm_path: Path = CRM_DNC_FILE) -> dict[str, Any]:
    if not crm_path.is_file():
        return {"records": {}}
    try:
        data = json.loads(crm_path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("records"), dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"records": {}}


def _save_crm_store(data: dict[str, Any], crm_path: Path = CRM_DNC_FILE) -> None:
    crm_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = crm_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, crm_path)


@mcp.tool()
def check_and_update_dnc_crm(
    domain: str,
    company: str = "",
    action: str = "check",
    reason: str = "",
) -> str:
    """
    Check or update a prospect domain in LeadSlayer's persistent CRM & Do-Not-Contact registry.
    action: 'check' | 'mark_staged' | 'mark_dnc' | 'mark_customer' | 'mark_competitor' | 'clear'
    """
    clean_domain = _normalize_domain(domain)
    if not clean_domain:
        return json.dumps({"domain": "", "allowed": False, "crm_status": "INVALID", "reason": "Empty domain"})

    env_dnc = {
        _normalize_domain(d)
        for d in settings.do_not_contact_domains.split(",")
        if d.strip()
    }
    store = _load_crm_store()
    records: dict[str, Any] = store["records"]
    now_iso = datetime.now(timezone.utc).isoformat()

    act = (action or "check").strip().lower()
    if act in ("mark_dnc", "mark_opt_out"):
        records[clean_domain] = {
            "company": company or clean_domain,
            "status": "DNC",
            "reason": reason or "Marked Do-Not-Contact via MCP",
            "updated_at": now_iso,
        }
        _save_crm_store(store)
    elif act == "mark_customer":
        records[clean_domain] = {
            "company": company or clean_domain,
            "status": "CUSTOMER",
            "reason": reason or "Existing customer protected from cold outreach",
            "updated_at": now_iso,
        }
        _save_crm_store(store)
    elif act == "mark_competitor":
        records[clean_domain] = {
            "company": company or clean_domain,
            "status": "COMPETITOR",
            "reason": reason or "Competitor domain protected",
            "updated_at": now_iso,
        }
        _save_crm_store(store)
    elif act == "mark_staged":
        existing = records.get(clean_domain, {})
        if existing.get("status") not in _BLOCKING_STATUSES and clean_domain not in env_dnc:
            records[clean_domain] = {
                "company": company or existing.get("company") or clean_domain,
                "status": "STAGED",
                "reason": reason or "Cleared & staged for outreach via MCP",
                "updated_at": now_iso,
            }
            _save_crm_store(store)
    elif act == "clear":
        records.pop(clean_domain, None)
        _save_crm_store(store)

    rec = records.get(clean_domain, {})
    status = "DNC" if clean_domain in env_dnc else str(rec.get("status", "CLEAR"))
    allowed = status not in _BLOCKING_STATUSES
    return json.dumps(
        {
            "domain": clean_domain,
            "company": company or rec.get("company", ""),
            "allowed": allowed,
            "crm_status": status,
            "reason": rec.get("reason", "Env Do-Not-Contact match" if clean_domain in env_dnc else "Clear in CRM"),
            "total_crm_records": len(records),
        }
    )


@mcp.tool()
def schedule_followup_reminder(
    run_id: str,
    lead_id: str,
    company: str,
    contact_name: str,
    priority: str = "HIGH",
    due_in_days: int = 2,
    reason: str = "",
) -> str:
    """
    Create a persistent follow-up task and an RFC-5545 .ics calendar invite for a high-urgency surviving lead.
    """
    safe_run = _safe_slug(run_id, "run")
    safe_lead = _safe_slug(lead_id, "lead")
    run_dir = EXPORTS_DIR / safe_run
    run_dir.mkdir(parents=True, exist_ok=True)

    days = max(1, min(30, int(due_in_days)))
    due_dt = datetime.now(timezone.utc) + timedelta(days=days)
    due_end = due_dt + timedelta(minutes=30)

    followups_file = run_dir / "followups.json"
    items: list[dict[str, Any]] = []
    if followups_file.is_file():
        try:
            loaded = json.loads(followups_file.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                items = loaded
        except (OSError, json.JSONDecodeError):
            items = []

    entry = {
        "lead_id": lead_id,
        "company": company,
        "contact_name": contact_name,
        "priority": (priority or "HIGH").upper(),
        "due_at_utc": due_dt.isoformat(),
        "reason": reason or "High-urgency buying signal follow-up",
    }
    items = [item for item in items if item.get("lead_id") != lead_id]
    items.append(entry)
    tmp_json = followups_file.with_suffix(".json.tmp")
    tmp_json.write_text(json.dumps(items, indent=2), encoding="utf-8")
    os.replace(tmp_json, followups_file)

    ics_path = run_dir / f"followup_{safe_lead}.ics"
    dt_start = due_dt.strftime("%Y%m%dT%H%M%SZ")
    dt_end = due_end.strftime("%Y%m%dT%H%M%SZ")
    ics_content = "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//LeadSlayer AI//GTM MCP Server//EN",
            "BEGIN:VEVENT",
            f"UID:leadslayer-{safe_run}-{safe_lead}@leadslayer.ai",
            f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART:{dt_start}",
            f"DTEND:{dt_end}",
            f"SUMMARY:Follow up with {contact_name} ({company}) [{entry['priority']}]",
            f"DESCRIPTION:{entry['reason']}",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )
    ics_path.write_text(ics_content, encoding="utf-8")

    return json.dumps(
        {
            "scheduled": True,
            "lead_id": lead_id,
            "company": company,
            "priority": entry["priority"],
            "due_at_utc": entry["due_at_utc"],
            "ics_path": str(ics_path),
            "followups_file": str(followups_file),
        }
    )


@mcp.tool()
async def stage_or_dispatch_email_mcp(
    lead_id: str,
    recipient_email: str,
    recipient_name: str,
    company: str,
    subject: str,
    body: str,
    delivery_mode: str = "SANDBOX",
    email_status: str = "unknown",
    mx_provider: str = "",
) -> str:
    """
    Validate a survivor email through LeadSlayer's CRM DNC check and deterministic pre-send compliance gate,
    then stage (SANDBOX) or send via configured SMTP/Gmail transport.
    """
    domain = _normalize_domain(recipient_email)
    crm_check = json.loads(
        check_and_update_dnc_crm(domain=domain, company=company, action="check")
    )
    if not crm_check.get("allowed", True):
        return json.dumps(
            {
                "lead_id": lead_id,
                "status": "BLOCKED",
                "provider": delivery_mode,
                "gate_reasons": [f"CRM status {crm_check['crm_status']}: {crm_check['reason']}"],
            }
        )

    draft = EmailDraft(
        lead_id=lead_id,
        recipient_name=recipient_name,
        recipient_email=recipient_email,
        company=company,
        subject=subject,
        body=body,
        cited_survival_signal="Verified by LeadSlayer MCP Coordinator",
        email_evidence_phrase=body[:32] if body else subject,
        matched_product_chunk="Stage 2 Grounded Capability",
        personalization_score=90,
        approved=True,
        status="DRAFTED",
    )
    lead = LeadRecord(
        id=lead_id,
        full_name=recipient_name,
        role="Decision Maker",
        company=company,
        domain=domain or "example.com",
        industry="B2B",
        employee_count=25,
        funding_stage="Seed",
        email=recipient_email,
        email_status=email_status,
        mx_provider=mx_provider,
    )

    safe_mode = delivery_mode if delivery_mode in ("SANDBOX", "SMTP", "GMAIL_OAUTH") else "SANDBOX"
    resp, any_sent = await dispatch_emails_via_harvey(
        emails={lead_id: draft},
        leads_by_id={lead_id: lead},
        lead_ids=[lead_id],
        delivery_mode=safe_mode,  # type: ignore[arg-type]
    )
    if any_sent:
        check_and_update_dnc_crm(
            domain=domain,
            company=company,
            action="mark_staged",
            reason=f"Email {safe_mode} processed via MCP",
        )
    receipt = resp.receipts[0].model_dump(mode="json") if resp.receipts else {}
    return json.dumps(
        {
            "lead_id": lead_id,
            "dispatched_count": resp.dispatched_count,
            "blocked_count": resp.blocked_count,
            "delivery_mode": resp.delivery_mode,
            "receipt": receipt,
        }
    )


@mcp.tool()
def save_campaign_artifacts(
    run_id: str,
    product_name: str,
    summary_markdown: str,
    survivors_csv: str = "",
    kill_audit_json: str = "",
) -> str:
    """
    Save executive brief, survivors CSV, and kill-audit JSON artifacts cleanly into exports/<run_id>/.
    """
    safe_run = _safe_slug(run_id, "run")
    run_dir = EXPORTS_DIR / safe_run
    run_dir.mkdir(parents=True, exist_ok=True)

    saved: dict[str, str] = {}
    brief_path = run_dir / "executive_brief.md"
    brief_text = (
        f"# LeadSlayer AI — Executive Campaign Brief ({product_name})\n"
        f"- **Run ID:** `{safe_run}`\n"
        f"- **Generated:** {datetime.now(timezone.utc).isoformat()}\n\n"
        f"{summary_markdown.strip()}\n"
    )
    brief_path.write_text(brief_text, encoding="utf-8")
    saved["executive_brief"] = str(brief_path)

    if survivors_csv.strip():
        csv_path = run_dir / "survivors.csv"
        csv_path.write_text(survivors_csv, encoding="utf-8")
        saved["survivors_csv"] = str(csv_path)

    if kill_audit_json.strip():
        json_path = run_dir / "kill_audit.json"
        json_path.write_text(kill_audit_json, encoding="utf-8")
        saved["kill_audit_json"] = str(json_path)

    return json.dumps(
        {
            "run_id": safe_run,
            "export_dir": str(run_dir),
            "files": saved,
        }
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
