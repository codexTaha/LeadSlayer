from __future__ import annotations

import csv
import io
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.config import EXPORTS_DIR

if TYPE_CHECKING:
    from app.models.schemas import EmailDraft, LeadRecord, SlayerVerdict
    from app.streaming.run_manager import RunState


def build_verified_leads_csv(
    leads: list["LeadRecord"],
    verdicts: dict[str, "SlayerVerdict"],
    emails: dict[str, "EmailDraft"],
) -> str:
    """Builds RFC-4180 CSV of all surviving/verified (and resurrected) leads + emails."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "lead_id",
            "full_name",
            "role",
            "company",
            "domain",
            "industry",
            "funding_stage",
            "email",
            "email_status",
            "mx_provider",
            "source_channel",
            "linkedin_url",
            "employee_count",
            "tech_stack",
            "recent_signal",
            "qualification_score",
            "icp_similarity_score",
            "resurrected_by_user",
            "matched_icp_id",
            "cited_survival_signal",
            "email_subject",
            "email_body",
            "dispatch_status",
        ]
    )

    for lead in leads:
        verdict = verdicts.get(lead.id)
        if verdict is None or not verdict.survived:
            continue
        draft = emails.get(lead.id)
        writer.writerow(
            [
                lead.id,
                lead.full_name,
                lead.role,
                lead.company,
                lead.domain,
                lead.industry,
                lead.funding_stage,
                lead.email,
                lead.email_status,
                lead.mx_provider,
                lead.source_channel,
                lead.linkedin_url,
                lead.employee_count,
                "; ".join(lead.tech_stack),
                lead.recent_signal,
                verdict.qualification_score,
                round(verdict.icp_similarity_score, 4),
                verdict.resurrected_by_user,
                verdict.matched_icp_id or "",
                draft.cited_survival_signal if draft else "",
                draft.subject if draft else "",
                draft.body if draft else "",
                draft.status if draft else "NOT_DRAFTED",
            ]
        )

    return buffer.getvalue()


def build_survivors_csv(run_state: "RunState") -> str:
    """Builds RFC-4180 CSV of all surviving (and resurrected) leads + emails."""
    return build_verified_leads_csv(run_state.leads, run_state.verdicts, run_state.emails)


def persist_verified_leads_csv(
    run_id: str,
    leads: list["LeadRecord"],
    verdicts: dict[str, "SlayerVerdict"],
    emails: dict[str, "EmailDraft"],
    exports_dir: Path = EXPORTS_DIR,
) -> Path:
    """Atomically writes exports/<run_id>/verified_leads.csv with all verified survivors."""
    safe_run = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in run_id).strip("_") or "run"
    run_dir = exports_dir / safe_run
    run_dir.mkdir(parents=True, exist_ok=True)
    csv_path = run_dir / "verified_leads.csv"
    tmp_path = run_dir / "verified_leads.csv.tmp"
    tmp_path.write_text(build_verified_leads_csv(leads, verdicts, emails), encoding="utf-8")
    os.replace(tmp_path, csv_path)
    return csv_path


def build_kill_audit_json(run_state: "RunState") -> dict[str, Any]:
    """Builds complete forensic audit log of all 50 leads, verdicts & emails."""
    entries: list[dict[str, Any]] = []
    for lead in run_state.leads:
        verdict = run_state.verdicts.get(lead.id)
        draft = run_state.emails.get(lead.id)
        entries.append(
            {
                "lead": lead.model_dump(mode="json"),
                "verdict": verdict.model_dump(mode="json") if verdict else None,
                "email_draft": draft.model_dump(mode="json") if draft else None,
            }
        )

    return {
        "run_id": run_state.run_id,
        "phase": run_state.phase.value,
        "startup": run_state.startup_input.model_dump(mode="json", exclude={"leads"}),
        "market_audit": (
            run_state.market_audit.model_dump(mode="json")
            if run_state.market_audit
            else None
        ),
        "icps": [icp.model_dump(mode="json") for icp in run_state.icps],
        "hunter_report": (
            run_state.hunter_report.model_dump(mode="json")
            if run_state.hunter_report
            else None
        ),
        "telemetry": run_state.telemetry.snapshot().model_dump(mode="json"),
        "leads_audit": entries,
    }
