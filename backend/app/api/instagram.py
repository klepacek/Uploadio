import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update

from app.core.auth import CurrentUser, CurrentWorkspace, Db
from app.core.config import get_settings
from app.core.crypto import encrypt
from app.integrations import instagram
from app.integrations.tiktok import PlatformError
from app.models.entities import OAuthState, SocialAccount


async def connect(db: Db, user: CurrentUser, workspace: CurrentWorkspace):
    settings = get_settings()
    if not settings.instagram_app_id or not settings.instagram_app_secret:
        raise HTTPException(503, "Instagram OAuth is not configured")
    state = secrets.token_urlsafe(32)
    db.add(
        OAuthState(
            workspace_id=workspace.id,
            user_id=user.id,
            platform="instagram",
            digest=hashlib.sha256(state.encode()).hexdigest(),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
    )
    query = urlencode(
        {
            "client_id": settings.instagram_app_id,
            "response_type": "code",
            "redirect_uri": f"{settings.api_url}/api/v1/oauth/instagram/callback",
            "state": state,
            "scope": "instagram_business_basic,instagram_business_content_publish",
        }
    )
    return {"url": f"https://www.instagram.com/oauth/authorize?{query}"}


async def callback(state: str, code: str, error: str, db: Db):
    row = (
        await db.execute(
            update(OAuthState)
            .where(
                OAuthState.digest == hashlib.sha256(state.encode()).hexdigest(),
                OAuthState.platform == "instagram",
                OAuthState.consumed_at.is_(None),
                OAuthState.expires_at > datetime.now(UTC),
            )
            .values(consumed_at=datetime.now(UTC))
            .returning(OAuthState)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(400, "OAuth state expired or already used")
    await db.commit()
    settings = get_settings()
    if error or not code:
        return RedirectResponse(
            f"{settings.frontend_url}/accounts?connection=denied", status_code=303
        )
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            tokens, scopes = await instagram.exchange(
                client, code, f"{settings.api_url}/api/v1/oauth/instagram/callback"
            )
            profile = await instagram.request(
                client,
                "GET",
                "me",
                tokens["access_token"],
                {"fields": "user_id,username,account_type"},
            )
        account_type = profile["account_type"].upper()
        if account_type not in {"BUSINESS", "MEDIA_CREATOR"}:
            raise HTTPException(422, "Instagram publishing requires a professional account")
        external_id = str(profile["user_id"])
        account = await db.scalar(
            select(SocialAccount)
            .where(
                SocialAccount.workspace_id == row.workspace_id,
                SocialAccount.platform == "instagram",
                SocialAccount.external_id == external_id,
            )
            .with_for_update()
        )
        if account is None:
            account = SocialAccount(
                workspace_id=row.workspace_id,
                platform="instagram",
                external_id=external_id,
                username=profile["username"],
            )
            db.add(account)
        account.access_token = encrypt(tokens["access_token"])
        account.refresh_token = None
        account.scopes = scopes
        account.expires_at = datetime.now(UTC) + timedelta(seconds=tokens["expires_in"])
        account.status = "connected"
        account.details = {"account_type": account_type}
        await db.commit()
    except (httpx.HTTPError, PlatformError, KeyError, ValueError) as exc:
        raise HTTPException(502, "Could not connect Instagram; start the connection again") from exc
    return RedirectResponse(f"{settings.frontend_url}/accounts?connection=success", status_code=303)
