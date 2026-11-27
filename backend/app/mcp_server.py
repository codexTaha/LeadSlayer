"""LeadSlayer Operational & Campaign MCP Server (stdio transport via mcp 2.x MCPServer)."""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import CRM_DNC_FILE, DATA_DIR, EXPORTS_DIR, settings  # noqa: E402
from app.harvey_bridge.dispatcher import dispatch_emails_via_harvey, get_mail_status  # noqa: E402
from app.models.schemas import (  # noqa: E402
    EmailDraft,
    ExecutionMode,
    LeadRecord,
    RunStateSnapshot,
    SlayerVerdict,
    SlayingLevel,
    StartupInput,
)
from app.services.lead_loader import load_preset_leads  # noqa: E402
from app.streaming.exporter import persist_verified_leads_csv  # noqa: E402

mcp = MCPServer(
    name="leadslayer-ops-mcp",
    instructions=(
        "LeadSlayer AI Autonomous GTM & Outreach MCP Server. "
        "When the user asks to find or bring X leads for a product/company, ALWAYS call `run_leadslayer_campaign`, "
        "then paste ALL returned `numbered_survivors` as a clean numbered list (#1, #2, ...) showing name, role, "
        "company, email, score, and drafted email subject, and ask the user whether to send/simulate emails to "
        "`all` of them or specific numbers (e.g. `1, 3, 5`). When the user replies with `all` or numbers, call "
        "`dispatch_campaign_emails(run_id=..., selection=...)` — which sends real emails if a sender mailbox is "
        "attached, or runs a verified Sandbox compliance simulation and saves artifacts if no mailbox is attached."
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


class _SilentMCPCallbacks:
    """Collects pipeline events in memory without writing anything to stdout."""

    def __init__(self) -> None:
        self.logs: list[str] = []
        self.leads: list[LeadRecord] = []

    async def on_phase(self, phase) -> None:
        pass

    async def on_log(self, message: str) -> None:
        self.logs.append(message)

    async def on_model_call(self, model_id) -> None:
        pass

    async def on_audit(self, audit) -> None:
        pass

    async def on_icps(self, icps) -> None:
        pass

    async def on_leads_loaded(self, leads: list[LeadRecord]) -> None:
        self.leads = list(leads)

    async def on_hunter_report(self, report) -> None:
        pass

    async def on_verdict(self, verdict) -> None:
        pass

    async def on_email(self, draft) -> None:
        pass

    async def on_mcp_tool_call(self, record) -> None:
        pass


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


@mcp.tool()
async def run_leadslayer_campaign(
    product_name: str,
    description: str,
    founder_assumptions: str = "Any B2B company in our target market needs this product.",
    product_url: str = "",
    target_qualified_leads: int = 10,
    slaying_level: str = "RUTHLESS",
    lead_sources: str = "AI_SEARCH,LINKEDIN_SEARCH",
    execution_mode: str = "LIVE",
) -> str:
    """
    Run the complete LeadSlayer AI multi-agent GTM pipeline (MarketAuditor -> ICP -> Hunter -> Slayer -> Sniper)
    and return a numbered list (#1..#N) of qualified surviving leads with drafted email previews so the user
    can choose 'all' or specific numbers to dispatch via `dispatch_campaign_emails`.
    execution_mode: 'LIVE' (runs live Gemini + discovery) or 'SAFE_REPLAY' (uses recorded snapshot at $0).
    """
    run_id = uuid.uuid4().hex[:12]
    safe_run = _safe_slug(run_id, "run")
    target_cap = max(1, min(50, int(target_qualified_leads)))
    level = SlayingLevel(slaying_level.upper()) if slaying_level.upper() in ("LENIENT", "NORMAL", "RUTHLESS") else SlayingLevel.RUTHLESS
    mode = ExecutionMode.SAFE_REPLAY if execution_mode.upper() == "SAFE_REPLAY" else ExecutionMode.LIVE

    raw_sources = [s.strip().upper() for s in lead_sources.split(",") if s.strip()]
    valid_sources = [s for s in raw_sources if s in ("AI_SEARCH", "LINKEDIN_SEARCH", "CSV_PRESET")]
    if not valid_sources:
        valid_sources = ["AI_SEARCH", "LINKEDIN_SEARCH"]

    startup = StartupInput(
        product_name=product_name.strip() or "Target Product",
        product_url=product_url.strip() or None,
        description=description.strip() if len(description.strip()) >= 20 else f"{description.strip()} — B2B solution for enterprise teams.",
        founder_assumptions=founder_assumptions.strip() if len(founder_assumptions.strip()) >= 5 else "Any company in this vertical is a good fit.",
        slaying_level=level,
        execution_mode=mode,
        lead_sources=valid_sources,  # type: ignore[arg-type]
        auto_discover_leads=("AI_SEARCH" in valid_sources or "LINKEDIN_SEARCH" in valid_sources),
        target_lead_count=min(30, max(5, target_cap)),
        target_qualified_leads=target_cap,
    )

    callbacks = _SilentMCPCallbacks()
    if mode == ExecutionMode.SAFE_REPLAY:
        replay_path = DATA_DIR / "replay_snapshot.json"
        if not replay_path.is_file():
            return json.dumps({"error": "SAFE_REPLAY requested but data/replay_snapshot.json is missing."})
        raw = json.loads(replay_path.read_text(encoding="utf-8"))
        snap = RunStateSnapshot.model_validate(raw["snapshot"])
        leads = list(snap.leads)
        verdicts = dict(snap.verdicts)
        emails = dict(snap.emails)
        market_audit = snap.market_audit
        icps = list(snap.icps)
    else:
        from app.agents.pipeline import run_live_pipeline

        initial_leads = load_preset_leads() if valid_sources == ["CSV_PRESET"] else []
        res = await run_live_pipeline(safe_run, startup, initial_leads, callbacks)
        leads = callbacks.leads or initial_leads
        verdicts = res.verdicts
        emails = res.emails
        market_audit = res.market_audit
        icps = res.icps

    leads_by_id = {l.id: l for l in leads}
    survivors_raw = [
        (l, verdicts[l.id], emails.get(l.id))
        for l in leads
        if l.id in verdicts and verdicts[l.id].survived
    ]
    # Keep top `target_cap` qualified survivors ordered by qualification_score desc
    survivors_raw.sort(key=lambda item: item[1].qualification_score, reverse=True)
    selected_survivors = survivors_raw[:target_cap]

    numbered_survivors: list[dict[str, Any]] = []
    for idx, (lead, verdict, draft) in enumerate(selected_survivors, start=1):
        leads_by_id[lead.id] = lead
        numbered_survivors.append(
            {
                "index": idx,
                "lead_id": lead.id,
                "full_name": lead.full_name,
                "role": lead.role,
                "company": lead.company,
                "domain": lead.domain,
                "email": lead.email,
                "email_status": lead.email_status,
                "mx_provider": lead.mx_provider,
                "qualification_score": verdict.qualification_score,
                "recent_signal": lead.recent_signal[:160],
                "email_subject": draft.subject if draft else f"Quick note for {lead.company}",
                "email_body_preview": (draft.body[:180] + "...") if draft and len(draft.body) > 180 else (draft.body if draft else ""),
            }
        )

    run_dir = EXPORTS_DIR / safe_run
    run_dir.mkdir(parents=True, exist_ok=True)
    state_file = run_dir / "run_state.json"
    state_payload = {
        "run_id": safe_run,
        "product_name": startup.product_name,
        "market_audit": market_audit.model_dump(mode="json") if market_audit else None,
        "icps": [i.model_dump(mode="json") for i in icps],
        "leads": {lid: l.model_dump(mode="json") for lid, l in leads_by_id.items()},
        "verdicts": {lid: v.model_dump(mode="json") for lid, v in verdicts.items()},
        "emails": {lid: d.model_dump(mode="json") for lid, d in emails.items()},
        "numbered_survivors": numbered_survivors,
    }
    tmp = state_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state_payload, indent=2), encoding="utf-8")
    os.replace(tmp, state_file)

    verified_csv_path = persist_verified_leads_csv(
        safe_run,
        list(leads_by_id.values()),
        verdicts,
        emails,
        exports_dir=EXPORTS_DIR,
    )

    mail_st = get_mail_status()
    mailbox_attached = bool(mail_st.smtp_configured or mail_st.gmail_configured)
    killed_n = sum(1 for v in verdicts.values() if not v.survived)

    return json.dumps(
        {
            "run_id": safe_run,
            "product_name": startup.product_name,
            "execution_mode": mode.value,
            "total_evaluated": len(verdicts),
            "killed_count": killed_n,
            "survivor_count": len(numbered_survivors),
            "verified_leads_csv": str(verified_csv_path),
            "mailbox_attached": mailbox_attached,
            "active_mail_provider": mail_st.active_provider,
            "sender_email": mail_st.smtp_sender or "Not attached (will run Sandbox simulation)",
            "numbered_survivors": numbered_survivors,
            "next_step_prompt": (
                "Paste ALL numbered_survivors above (#1..#N) and ask the user: "
                "'Reply `all` to send/simulate emails to every lead above, or paste specific numbers (e.g. `1, 3, 5`).'"
            ),
        }
    )


def _parse_lead_selection(selection: str, numbered: list[dict[str, Any]]) -> list[str]:
    clean = (selection or "all").strip().lower()
    if clean in ("", "all", "*"):
        return [item["lead_id"] for item in numbered]

    by_index = {str(item["index"]): item["lead_id"] for item in numbered}
    valid_ids = {item["lead_id"] for item in numbered}
    selected: list[str] = []
    for token in re.split(r"[\s,;]+", clean):
        tok = token.lstrip("#").strip()
        if not tok:
            continue
        if tok in by_index and by_index[tok] not in selected:
            selected.append(by_index[tok])
        elif tok in valid_ids and tok not in selected:
            selected.append(tok)
    return selected


@mcp.tool()
async def dispatch_campaign_emails(
    run_id: str,
    selection: str = "all",
    delivery_mode: str = "AUTO",
) -> str:
    """
    Send or simulate outreach emails for a completed `run_leadslayer_campaign` run.
    selection: 'all' OR comma/space-separated lead numbers like '1, 3, 5' OR lead IDs.
    delivery_mode: 'AUTO' (sends LIVE via SMTP/Gmail if mailbox attached, otherwise runs verified SANDBOX simulation),
                   or explicit 'SANDBOX' | 'SMTP' | 'GMAIL_OAUTH'.
    """
    safe_run = _safe_slug(run_id, "run")
    state_file = EXPORTS_DIR / safe_run / "run_state.json"
    if not state_file.is_file():
        return json.dumps({"error": f"Run '{safe_run}' not found. Run `run_leadslayer_campaign` first."})

    raw = json.loads(state_file.read_text(encoding="utf-8"))
    numbered = raw.get("numbered_survivors", [])
    target_ids = _parse_lead_selection(selection, numbered)
    if not target_ids:
        return json.dumps(
            {
                "error": f"No valid leads matched selection {selection!r}. Available numbers: 1..{len(numbered)}",
            }
        )

    leads_by_id = {lid: LeadRecord.model_validate(l) for lid, l in raw.get("leads", {}).items()}
    emails = {lid: EmailDraft.model_validate(d) for lid, d in raw.get("emails", {}).items()}

    # Ensure every selected survivor has a drafted EmailDraft fallback if needed
    for item in numbered:
        lid = item["lead_id"]
        if lid in target_ids and lid not in emails:
            emails[lid] = EmailDraft(
                lead_id=lid,
                recipient_name=item["full_name"],
                recipient_email=item["email"],
                company=item["company"],
                subject=item.get("email_subject") or f"Quick question for {item['company']}",
                body=f"Hi {item['full_name'].split()[0]}, noticed {item.get('recent_signal', 'your recent growth')}. Happy to share how {raw.get('product_name', 'we')} can help.",
                cited_survival_signal=item.get("recent_signal", "Active buyer signal"),
                email_evidence_phrase=item.get("recent_signal", "your recent growth")[:40],
                matched_product_chunk="Campaign Outreach",
                personalization_score=85,
            )

    mail_st = get_mail_status()
    mailbox_attached = bool(mail_st.smtp_configured or mail_st.gmail_configured)
    mode_req = (delivery_mode or "AUTO").strip().upper()
    if mode_req == "AUTO":
        effective_mode = "SMTP" if mail_st.smtp_configured else ("GMAIL_OAUTH" if mail_st.gmail_configured else "SANDBOX")
    elif mode_req in ("SANDBOX", "SMTP", "GMAIL_OAUTH"):
        effective_mode = mode_req
    else:
        effective_mode = "SANDBOX"

    resp, any_sent = await dispatch_emails_via_harvey(
        emails=emails,
        leads_by_id=leads_by_id,
        lead_ids=target_ids,
        delivery_mode=effective_mode,  # type: ignore[arg-type]
        product_name=raw.get("product_name", "LeadSlayer"),
    )

    for lid in target_ids:
        lead = leads_by_id.get(lid)
        if lead is not None:
            check_and_update_dnc_crm(
                domain=lead.domain,
                company=lead.company,
                action="mark_staged",
                reason=f"Processed via dispatch_campaign_emails ({effective_mode})",
            )

    # Persist updated emails & dispatch receipts on disk for proof/audit
    raw["emails"] = {lid: d.model_dump(mode="json") for lid, d in emails.items()}
    tmp = state_file.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    os.replace(tmp, state_file)

    receipts_file = EXPORTS_DIR / safe_run / "dispatch_receipts.json"
    receipts_file.write_text(resp.model_dump_json(indent=2), encoding="utf-8")

    verdicts_map = {
        lid: SlayerVerdict.model_validate(v)
        for lid, v in raw.get("verdicts", {}).items()
    }
    verified_csv_path = persist_verified_leads_csv(
        safe_run,
        list(leads_by_id.values()),
        verdicts_map,
        emails,
        exports_dir=EXPORTS_DIR,
    )

    summary_lines = [
        f"- **Delivery Mode:** `{effective_mode}` ({'Real Inbox Delivery' if effective_mode != 'SANDBOX' else 'Safe Sandbox Simulation — No external mailbox attached'})",
        f"- **Selected Leads:** {len(target_ids)}",
        f"- **Processed / Verified:** {resp.dispatched_count}",
        f"- **Blocked by Compliance/DNC Gate:** {resp.blocked_count}",
    ]
    save_campaign_artifacts(
        run_id=safe_run,
        product_name=raw.get("product_name", "LeadSlayer"),
        summary_markdown="\n".join(summary_lines),
        survivors_csv=verified_csv_path.read_text(encoding="utf-8"),
    )

    return json.dumps(
        {
            "run_id": safe_run,
            "mode_executed": "SANDBOX_SIMULATION" if effective_mode == "SANDBOX" else f"LIVE_{effective_mode}",
            "mailbox_attached": mailbox_attached,
            "selected_lead_ids": target_ids,
            "dispatched_count": resp.dispatched_count,
            "blocked_count": resp.blocked_count,
            "verified_leads_csv": str(verified_csv_path),
            "receipts_file": str(receipts_file),
            "receipts": [r.model_dump(mode="json") for r in resp.receipts],
            "verification_summary": (
                f"Sent {resp.dispatched_count} live email(s) via {effective_mode}."
                if effective_mode != "SANDBOX"
                else f"No sender mailbox attached — ran verified SANDBOX simulation: {resp.dispatched_count} passed compliance & CRM DNC gates, {resp.blocked_count} blocked. Receipts saved to {receipts_file}."
            ),
        }
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
