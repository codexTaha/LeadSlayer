"""Tier C bridge connecting Harvey's deterministic send gate and Gmail/SMTP providers."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.config import HARVEY_ROOT, settings
from app.harvey_bridge import ensure_harvey_on_path
from app.models.schemas import (
    DeliveryMode,
    DispatchReceipt,
    DispatchResponse,
    EmailDraft,
    HarveyStatusResponse,
    LeadRecord,
    PipelinePhase,
)

ensure_harvey_on_path()

from harvey.gate import do_not_contact_entries, pre_send_check  # noqa: E402
from harvey.integrations.gmail import GmailProvider, TOKEN_FILE as HARVEY_GMAIL_TOKEN_FILE  # noqa: E402
from harvey.integrations.smtp_mail import SmtpImapProvider  # noqa: E402


def _build_harvey_config_and_env(product_name: str = "LeadSlayer"):
    from_email = settings.smtp_from_email or settings.smtp_username or "outreach@leadslayer.ai"
    config = SimpleNamespace(
        persona=SimpleNamespace(
            name=settings.smtp_from_name or "LeadSlayer",
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
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_username=settings.smtp_username,
        smtp_password=settings.smtp_password,
        imap_host=settings.imap_host or settings.smtp_host,
        imap_port=settings.imap_port,
        imap_username=settings.smtp_username,
        imap_password=settings.smtp_password,
        gmail_client_id=settings.gmail_client_id,
        gmail_client_secret=settings.gmail_client_secret,
    )
    return config, env


def _parse_dnc_list() -> list[str]:
    if not settings.do_not_contact_domains.strip():
        return []
    try:
        return do_not_contact_entries(settings.do_not_contact_domains)
    except ValueError:
        return [x.strip().lower() for x in settings.do_not_contact_domains.split(",") if x.strip()]


def get_harvey_status() -> HarveyStatusResponse:
    config, env = _build_harvey_config_and_env()
    smtp_provider = SmtpImapProvider(config, env)
    gmail_provider = GmailProvider(config, env)
    try:
        import playwright  # noqa: F401

        has_pw = True
    except ImportError:
        has_pw = False

    return HarveyStatusResponse(
        harvey_connected=HARVEY_ROOT.exists(),
        smtp_configured=smtp_provider.is_configured(),
        gmail_configured=gmail_provider.is_configured() or HARVEY_GMAIL_TOKEN_FILE.is_file(),
        linkedin_playwright_configured=bool(
            has_pw and settings.linkedin_email and settings.linkedin_password
        ),
        smtp_sender=settings.smtp_from_email or settings.smtp_username,
        do_not_contact_count=len(_parse_dnc_list()),
    )


async def dispatch_emails_via_harvey(
    emails: dict[str, EmailDraft],
    leads_by_id: dict[str, LeadRecord],
    lead_ids: list[str],
    delivery_mode: DeliveryMode = "SANDBOX",
    product_name: str = "LeadSlayer",
) -> tuple[DispatchResponse, bool]:
    """
    Runs Harvey's deterministic pre_send_check on every approved draft, and either:
    - SANDBOX: marks validated drafts SENT locally ($0, safe testing), blocking only DNC matches
    - HARVEY_SMTP / HARVEY_GMAIL: sends real mail through Harvey's provider after passing all gate checks
    """
    config, env = _build_harvey_config_and_env(product_name=product_name)
    dnc_list = _parse_dnc_list()
    postal = settings.sender_postal_address.strip()

    provider = None
    if delivery_mode == "HARVEY_SMTP":
        provider = SmtpImapProvider(config, env)
        if not provider.is_configured():
            raise ValueError(
                "Harvey SMTP is not configured. Add SMTP_HOST, SMTP_USERNAME, and SMTP_PASSWORD in .env, or use Sandbox dispatch."
            )
    elif delivery_mode == "HARVEY_GMAIL":
        provider = GmailProvider(config, env)
        if not provider.is_configured():
            raise ValueError(
                "Harvey Gmail OAuth is not configured. Configure GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET and run 'harvey gmail auth', or use SMTP/Sandbox."
            )

    receipts: list[DispatchReceipt] = []
    sent_count = 0
    blocked_count = 0

    for lid in lead_ids:
        draft = emails.get(lid)
        if draft is None:
            continue

        lead = leads_by_id.get(lid)
        # Map lead to lightweight Harvey prospect object if live-sending
        prospect_proxy = None
        if delivery_mode != "SANDBOX" and lead is not None:
            # Allow sending to verified public emails or MX-verified guesses explicitly approved by user in Sniper Deck
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
        if postal and postal not in body_to_send and delivery_mode != "SANDBOX":
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

        # In SANDBOX mode, only hard-block explicit DNC / invalid email syntax; surface soft style notes cleanly
        if delivery_mode == "SANDBOX":
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

        # Live Harvey dispatch (HARVEY_SMTP or HARVEY_GMAIL) enforces ALL gate checks
        if not gate.ok:
            blocked_count += 1
            receipts.append(
                DispatchReceipt(
                    lead_id=lid,
                    recipient_email=draft.recipient_email,
                    status="BLOCKED",
                    provider=delivery_mode,
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
                    provider=delivery_mode,
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
                    provider=delivery_mode,
                    error=send_res.error,
                )
            )

    return (
        DispatchResponse(
            dispatched_count=sent_count,
            blocked_count=blocked_count,
            delivery_mode=delivery_mode,
            sent_at=datetime.now(timezone.utc).isoformat(),
            receipts=receipts,
        ),
        sent_count > 0,
    )
