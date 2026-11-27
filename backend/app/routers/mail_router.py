from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from app.harvey_bridge.dispatcher import get_mail_status
from app.models.schemas import MailStatusResponse, SMTPConnectRequest
from app.services.mail_account import (
    build_google_oauth_url,
    exchange_google_oauth_code,
    mail_account_store,
    verify_smtp_credentials,
)

mail_router = APIRouter(prefix="/api/mail", tags=["mail"])


@mail_router.get("/status", response_model=MailStatusResponse)
async def mail_status() -> MailStatusResponse:
    return get_mail_status()


@mail_router.post("/connect-smtp", response_model=MailStatusResponse)
async def connect_smtp(payload: SMTPConnectRequest) -> MailStatusResponse:
    if payload.verify_connection:
        try:
            await verify_smtp_credentials(
                email=payload.email,
                password=payload.password,
                smtp_host=payload.smtp_host,
                smtp_port=payload.smtp_port,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"SMTP login verification failed for {payload.smtp_host}:{payload.smtp_port}. "
                    f"For Gmail, ensure 2FA is enabled and use a 16-character App Password. ({exc})"
                ),
            ) from exc

    mail_account_store.connect_smtp(
        email=payload.email,
        password=payload.password,
        smtp_host=payload.smtp_host,
        smtp_port=payload.smtp_port,
        sender_name=payload.sender_name,
        postal_address=payload.postal_address,
    )
    return get_mail_status()


@mail_router.post("/disconnect", response_model=MailStatusResponse)
async def disconnect_mail() -> MailStatusResponse:
    mail_account_store.disconnect()
    return get_mail_status()


@mail_router.get("/oauth/google/start")
async def start_google_oauth(request: Request) -> RedirectResponse:
    callback_url = str(request.url_for("google_oauth_callback"))
    try:
        auth_url = build_google_oauth_url(redirect_uri=callback_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=auth_url)


@mail_router.get("/oauth/google/callback", name="google_oauth_callback")
async def google_oauth_callback(
    request: Request,
    code: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    if error:
        return RedirectResponse(url=f"/?mail_error={error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing Google OAuth authorization code.")
    callback_url = str(request.url_for("google_oauth_callback"))
    try:
        await exchange_google_oauth_code(code=code, redirect_uri=callback_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url="/?mail_connected=gmail")
