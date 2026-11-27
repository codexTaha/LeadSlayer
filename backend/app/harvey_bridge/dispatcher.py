"""Deliverability gate, DNC enforcement, and SMTP/Gmail OAuth transport bridge."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

from app.config import CRM_DNC_FILE, GMAIL_OAUTH_TOKEN_FILE, HARVEY_ROOT, settings
from app.harvey_bridge import ensure_harvey_on_path
from app.models.schemas import (
    DeliveryMode,
    DispatchReceipt,
    DispatchResponse,
    EmailDraft,
    LeadRecord,
    MailStatusResponse,
)
from app.services.mail_account import mail_account_store, mask_email

ensure_harvey_on_path()

import harvey.integrations.gmail as _gmail_mod  # noqa: E402
from harvey.gate import do_not_contact_entries, pre_send_check  # noqa: E402
from harvey.integrations.gmail import GmailProvider  # noqa: E402
from harvey.integrations.smtp_mail import SmtpImapProvider  # noqa: E402


def _sync_gmail_token_path() -> None:
    if GMAIL_OAUTH_TOKEN_FILE.is_file():
        _gmail_mod.TOKEN_FILE = GMAIL_OAUTH_TOKEN_FILE


def _normalize_delivery_mode(mode: DeliveryMode) -> str:
    if mode in ("SMTP", "HARVEY_SMTP"):
        return "SMTP"
    if mode in ("GMAIL_OAUTH", "HARVEY_GMAIL"):
        return "GMAIL_OAUTH"
    return "SANDBOX"


def _build_harvey_config_and_env(product_name: str = "LeadSlayer"):
    mailbox = mail_account_store.get_effective()
    from_email = mailbox.email or settings.smtp_from_email or settings.smtp_username or "outreach@leadslayer.ai"
    sender_name = mailbox.sender_name or settings.smtp_from_name or "LeadSlayer"
    smtp_host = mailbox.smtp_host
    smtp_port = mailbox.smtp_port
    smtp_user = mailbox.email if mailbox.source == "ui_smtp" else settings.smtp_username
    smtp_pass = mailbox.password

    config = SimpleNamespace(
        persona=SimpleNamespace(
            name=sender_name,
            company=product_name,
            email=from_email,
        ),
        channels=SimpleNamespace(
            email=SimpleNamespace(
                enabled=True,
                signature=SimpleNamespace(logo="", width=120, alt="", link="", direction="auto"),
            )
        ),
    )
    env = SimpleNamespace(
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_username=smtp_user,
        smtp_password=smtp_pass,
        imap_host=settings.imap_host or smtp_host,
        imap_port=settings.imap_port,
        imap_username=smtp_user,
        imap_password=smtp_pass,
        gmail_client_id=settings.gmail_client_id,
        gmail_client_secret=settings.gmail_client_secret,
    )
    return config, env


def _parse_dnc_list() -> list[str]:
    entries: list[str] = []
    if settings.do_not_contact_domains.strip():
        try:
            entries.extend(do_not_contact_entries(settings.do_not_contact_domains))
        except ValueError:
            entries.extend(
                x.strip().lower()
                for x in settings.do_not_contact_domains.split(",")
                if x.strip()
            )
    if CRM_DNC_FILE.is_file():
        try:
            raw = json.loads(CRM_DNC_FILE.read_text(encoding="utf-8"))
            for domain, record in (raw.get("records") or {}).items():
                if isinstance(record, dict) and record.get("status") in (
                    "DNC",
                    "OPT_OUT",
                    "CUSTOMER",
                    "COMPETITOR",
                ):
                    clean = str(domain).strip().lower()
                    if clean and clean not in entries:
                        entries.append(clean)
        except (OSError, json.JSONDecodeError):
            pass
    return entries


def get_mail_status() -> MailStatusResponse:
    _sync_gmail_token_path()
    config, env = _build_harvey_config_and_env()
    smtp_provider = SmtpImapProvider(config, env)
    gmail_provider = GmailProvider(config, env)
    try:
        import playwright  # noqa: F401

        has_pw = True
    except ImportError:
        has_pw = False

    smtp_ok = smtp_provider.is_configured()
    gmail_ok = gmail_provider.is_configured()
    active_provider = "SMTP" if smtp_ok else ("GMAIL_OAUTH" if gmail_ok else "SANDBOX")
    mailbox = mail_account_store.get_effective()
    sender_display = mailbox.email or settings.smtp_from_email or settings.smtp_username

    return MailStatusResponse(
        mail_engine_ready=HARVEY_ROOT.exists(),
        smtp_configured=smtp_ok,
        gmail_configured=gmail_ok,
        gmail_oauth_available=bool(settings.gmail_client_id and settings.gmail_client_secret),
        linkedin_browser_configured=bool(
            has_pw and settings.linkedin_email and settings.linkedin_password
        ),
        active_provider=active_provider,
        smtp_sender=mask_email(sender_display) if sender_display else "",
        sender_name=mailbox.sender_name or settings.smtp_from_name or "LeadSlayer",
        do_not_contact_count=len(_parse_dnc_list()),
    )


get_harvey_status = get_mail_status


async def dispatch_emails_via_harvey(
    emails: dict[str, EmailDraft],
    leads_by_id: dict[str, LeadRecord],
    lead_ids: list[str],
    delivery_mode: DeliveryMode = "SANDBOX",
    product_name: str = "LeadSlayer",
) -> tuple[DispatchResponse, bool]:
    """
    Runs LeadSlayer's deterministic pre-send compliance gate on every approved draft, and either:
    - SANDBOX: marks validated drafts SENT locally ($0, safe testing), blocking only DNC/invalid matches
    - SMTP / GMAIL_OAUTH: sends real mail through the connected mailbox after passing all gate checks
    """
    _sync_gmail_token_path()
    normalized_mode = _normalize_delivery_mode(delivery_mode)
    config, env = _build_harvey_config_and_env(product_name=product_name)
    dnc_list = _parse_dnc_list()
    mailbox = mail_account_store.get_effective()
    postal = (mailbox.postal_address or settings.sender_postal_address).strip()

    provider = None
    if normalized_mode == "SMTP":
        provider = SmtpImapProvider(config, env)
        if not provider.is_configured():
            raise ValueError(
                "SMTP mailbox is not connected yet. Click 'Connect Email' to link Gmail App Password or custom SMTP, or use Sandbox dispatch."
            )
    elif normalized_mode == "GMAIL_OAUTH":
        provider = GmailProvider(config, env)
        if not provider.is_configured():
            raise ValueError(
                "Gmail OAuth is not connected yet. Click 'Connect Email -> Sign in with Google' (requires GMAIL_CLIENT_ID in .env) or use SMTP/Sandbox."
            )

    receipts: list[DispatchReceipt] = []
    sent_count = 0
    blocked_count = 0

    for lid in lead_ids:
        draft = emails.get(lid)
        if draft is None:
            continue

        lead = leads_by_id.get(lid)
        prospect_proxy = None
        if normalized_mode != "SANDBOX" and lead is not None:
            effective_status = "verified" if lead.email_status in ("verified", "public", "unknown") else lead.email_status
            if lead.email_status == "invalid" or lead.mx_provider == "none":
                effective_status = "invalid"
            elif lead.email_status == "guess" and lead.mx_provider in ("google", "microsoft", "other", "gateway"):
                effective_status = "risky"
            prospect_proxy = SimpleNamespace(
                email=draft.recipient_email,
                email_status=effective_status,
            )

        body_to_send = draft.body
        if postal and postal not in body_to_send and normalized_mode != "SANDBOX":
            body_to_send = f"{body_to_send.rstrip()}\n\n--\n{postal}"

        gate = pre_send_check(
            to_email=draft.recipient_email,
            subject=draft.subject,
            body=body_to_send,
            prospect=prospect_proxy,
            allow_risky=True,
            kind="sequence",
            postal_address=postal,
            do_not_contact=dnc_list,
        )

        if normalized_mode == "SANDBOX":
            hard_blocks = [
                r
                for r in gate.reasons
                if "do-not-contact" in r or "invalid recipient address" in r
            ]
            if hard_blocks:
                blocked_count += 1
                receipts.append(
                    DispatchReceipt(
                        lead_id=lid,
                        recipient_email=draft.recipient_email,
                        status="BLOCKED",
                        provider="SANDBOX",
                        gate_reasons=hard_blocks,
                    )
                )
                continue

            emails[lid] = draft.model_copy(update={"status": "SENT", "approved": True})
            sent_count += 1
            receipts.append(
                DispatchReceipt(
                    lead_id=lid,
                    recipient_email=draft.recipient_email,
                    status="SENT",
                    provider="SANDBOX",
                    gate_reasons=gate.reasons,
                )
            )
            continue

        if not gate.ok:
            blocked_count += 1
            receipts.append(
                DispatchReceipt(
                    lead_id=lid,
                    recipient_email=draft.recipient_email,
                    status="BLOCKED",
                    provider=normalized_mode,
                    gate_reasons=gate.reasons,
                )
            )
            continue

        assert provider is not None
        send_res = await provider.send_email(
            to_email=draft.recipient_email,
            subject=draft.subject,
            body=body_to_send,
        )
        if send_res.ok:
            emails[lid] = draft.model_copy(update={"status": "SENT", "approved": True})
            sent_count += 1
            receipts.append(
                DispatchReceipt(
                    lead_id=lid,
                    recipient_email=draft.recipient_email,
                    status="SENT",
                    provider=normalized_mode,
                    message_id=send_res.message_id,
                    gate_reasons=[],
                )
            )
        else:
            blocked_count += 1
            receipts.append(
                DispatchReceipt(
                    lead_id=lid,
                    recipient_email=draft.recipient_email,
                    status="FAILED",
                    provider=normalized_mode,
                    error=send_res.error,
                )
            )

    return (
        DispatchResponse(
            dispatched_count=sent_count,
            blocked_count=blocked_count,
            delivery_mode=normalized_mode,
            sent_at=datetime.now(timezone.utc).isoformat(),
            receipts=receipts,
        ),
        sent_count > 0,
    )


dispatch_emails_via_engine = dispatch_emails_via_harvey
