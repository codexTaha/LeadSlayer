from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.parse import urlencode

import aiosmtplib
import httpx

from app.config import GMAIL_OAUTH_TOKEN_FILE, settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.modify"


@dataclass
class RuntimeMailboxConfig:
    email: str = ""
    password: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    sender_name: str = "LeadSlayer"
    postal_address: str = ""
    source: str = "none"  # "none" | "env" | "ui_smtp" | "gmail_oauth"


class MailAccountStore:
    """In-memory runtime mailbox session store seeded safely from .env."""

    def __init__(self) -> None:
        self._runtime: RuntimeMailboxConfig | None = None

    def get_effective(self) -> RuntimeMailboxConfig:
        if self._runtime is not None:
            return self._runtime
        env_email = settings.smtp_from_email or settings.smtp_username
        if settings.smtp_host and settings.smtp_username and settings.smtp_password:
            return RuntimeMailboxConfig(
                email=env_email,
                password=settings.smtp_password,
                smtp_host=settings.smtp_host,
                smtp_port=settings.smtp_port,
                sender_name=settings.smtp_from_name or "LeadSlayer",
                postal_address=settings.sender_postal_address,
                source="env",
            )
        return RuntimeMailboxConfig(
            email=env_email,
            sender_name=settings.smtp_from_name or "LeadSlayer",
            postal_address=settings.sender_postal_address,
            source="none",
        )

    def connect_smtp(
        self,
        *,
        email: str,
        password: str,
        smtp_host: str,
        smtp_port: int,
        sender_name: str,
        postal_address: str = "",
    ) -> RuntimeMailboxConfig:
        cfg = RuntimeMailboxConfig(
            email=email.strip(),
            password=password,
            smtp_host=smtp_host.strip(),
            smtp_port=smtp_port,
            sender_name=sender_name.strip() or "LeadSlayer",
            postal_address=postal_address.strip(),
            source="ui_smtp",
        )
        self._runtime = cfg
        return cfg

    def disconnect(self) -> None:
        self._runtime = RuntimeMailboxConfig(source="none")
        if GMAIL_OAUTH_TOKEN_FILE.is_file():
            try:
                GMAIL_OAUTH_TOKEN_FILE.unlink()
            except OSError:
                pass


mail_account_store = MailAccountStore()


async def verify_smtp_credentials(
    *,
    email: str,
    password: str,
    smtp_host: str,
    smtp_port: int,
) -> None:
    """Tests live SMTP TLS connection and authentication without sending an email."""
    client = aiosmtplib.SMTP(
        hostname=smtp_host.strip(),
        port=smtp_port,
        use_tls=(smtp_port == 465),
        timeout=15.0,
    )
    await client.connect()
    try:
        if smtp_port == 587:
            await client.starttls()
        await client.login(email.strip(), password)
    finally:
        try:
            await client.quit()
        except Exception:
            pass


def mask_email(email: str) -> str:
    clean = (email or "").strip()
    if "@" not in clean:
        return clean
    local, domain = clean.split("@", 1)
    if len(local) <= 2:
        return f"{local[:1]}*@{domain}"
    return f"{local[:2]}{'*' * min(4, len(local) - 2)}@{domain}"


def build_google_oauth_url(redirect_uri: str, state: str = "leadslayer") -> str:
    if not settings.gmail_client_id or not settings.gmail_client_secret:
        raise ValueError(
            "Google OAuth client credentials (GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET) are not set in .env. "
            "Use SMTP / Gmail App Password connection instead."
        )
    params = {
        "client_id": settings.gmail_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GMAIL_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_google_oauth_code(code: str, redirect_uri: str) -> dict:
    if not settings.gmail_client_id or not settings.gmail_client_secret:
        raise ValueError("Missing GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET in .env.")

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.gmail_client_id,
                "client_secret": settings.gmail_client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if resp.status_code >= 400:
            raise ValueError(f"Google OAuth token exchange failed ({resp.status_code}).")
        token_data = resp.json()

    if not token_data.get("refresh_token") and not token_data.get("access_token"):
        raise ValueError("Google OAuth did not return a usable token.")

    GMAIL_OAUTH_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = GMAIL_OAUTH_TOKEN_FILE.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(token_data, indent=2), encoding="utf-8")
    os.replace(tmp_path, GMAIL_OAUTH_TOKEN_FILE)
    try:
        GMAIL_OAUTH_TOKEN_FILE.chmod(0o600)
    except OSError:
        pass
    return token_data
