from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

from app.config import DATA_DIR
from app.models.schemas import LeadRecord, StartupInput


HEADER_ALIASES: dict[str, str] = {
    "id": "id",
    "lead_id": "id",
    "full_name": "full_name",
    "name": "full_name",
    "contact_name": "full_name",
    "role": "role",
    "title": "role",
    "job_title": "role",
    "company": "company",
    "company_name": "company",
    "organization": "company",
    "domain": "domain",
    "website": "domain",
    "company_domain": "domain",
    "industry": "industry",
    "sector": "industry",
    "employee_count": "employee_count",
    "employees": "employee_count",
    "headcount": "employee_count",
    "company_size": "employee_count",
    "funding_stage": "funding_stage",
    "funding": "funding_stage",
    "stage": "funding_stage",
    "tech_stack": "tech_stack",
    "stack": "tech_stack",
    "technologies": "tech_stack",
    "recent_signal": "recent_signal",
    "signal": "recent_signal",
    "news": "recent_signal",
    "bio_snippet": "bio_snippet",
    "bio": "bio_snippet",
    "notes": "bio_snippet",
    "email": "email",
    "work_email": "email",
}


def _normalize_header(raw_header: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", raw_header.strip().lower()).strip("_")
    return HEADER_ALIASES.get(cleaned, cleaned)


def _parse_employee_count(raw_value: str | int | None) -> int:
    if isinstance(raw_value, int):
        return max(1, raw_value)
    text = str(raw_value or "").strip().replace(",", "")
    match = re.search(r"\d+", text)
    if not match:
        return 1
    return max(1, int(match.group(0)))


def _parse_tech_stack(raw_value: str | list[str] | None) -> list[str]:
    if isinstance(raw_value, list):
        return [item.strip() for item in raw_value if str(item).strip()]
    text = str(raw_value or "").strip()
    if not text:
        return []
    parts = re.split(r"[;|,]", text)
    return [p.strip() for p in parts if p.strip()]


def load_default_startup(data_dir: Path = DATA_DIR) -> StartupInput:
    path = data_dir / "default_startup.json"
    with path.open("r", encoding="utf-8") as f:
        return StartupInput.model_validate(json.load(f))


def load_preset_leads(data_dir: Path = DATA_DIR) -> list[LeadRecord]:
    path = data_dir / "leads_50.json"
    with path.open("r", encoding="utf-8") as f:
        raw_list = json.load(f)
    return [LeadRecord.model_validate(item) for item in raw_list]


def parse_leads_csv_bytes(raw_bytes: bytes) -> tuple[list[LeadRecord], list[str]]:
    text = raw_bytes.decode("utf-8-sig", errors="replace").strip()
    if not text:
        raise ValueError("Uploaded CSV file is empty.")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV file is missing a header row.")

    normalized_map = {orig: _normalize_header(orig) for orig in reader.fieldnames if orig}
    leads: list[LeadRecord] = []
    warnings: list[str] = []
    seen_emails: set[str] = set()

    for idx, row in enumerate(reader, start=1):
        mapped: dict[str, str] = {}
        for orig_col, value in row.items():
            if not orig_col:
                continue
            norm_key = normalized_map.get(orig_col, orig_col)
            if value is not None:
                mapped[norm_key] = value.strip()

        if not any(mapped.values()):
            continue

        lead_id = mapped.get("id") or f"lead_{idx:02d}"
        full_name = mapped.get("full_name") or f"Contact {idx}"
        company = mapped.get("company") or f"Company {idx}"
        domain = mapped.get("domain") or f"{re.sub(r'[^a-z0-9]', '', company.lower()) or 'company'}.io"
        email = mapped.get("email") or f"contact{idx}@{domain}"

        if email.lower() in seen_emails:
            warnings.append(f"Row {idx}: duplicate email '{email}' encountered.")
        seen_emails.add(email.lower())

        lead = LeadRecord(
            id=lead_id,
            full_name=full_name,
            role=mapped.get("role") or "Unknown Role",
            company=company,
            domain=domain,
            industry=mapped.get("industry") or "Technology",
            employee_count=_parse_employee_count(mapped.get("employee_count")),
            funding_stage=mapped.get("funding_stage") or "Seed",
            tech_stack=_parse_tech_stack(mapped.get("tech_stack")),
            recent_signal=mapped.get("recent_signal") or "",
            bio_snippet=mapped.get("bio_snippet") or "",
            email=email,
        )
        leads.append(lead)

    if not leads:
        raise ValueError("No valid lead rows found in uploaded CSV.")

    return leads, warnings
