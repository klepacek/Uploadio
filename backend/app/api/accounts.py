import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update

from app.core.auth import CurrentUser, CurrentWorkspace, Db
from app.core.config import get_settings
from app.core.crypto import encrypt
from app.integrations import tiktok
from app.models.entities import AuditLog, OAuthState, Post, PostTarget, SocialAccount
from app.services.accounts import access_token

router = APIRouter(prefix="/api/v1", tags=["social accounts"])


def public_account(account: SocialAccount):
    return {
        "id": account.id,
        "platform": account.platform,
        "username": account.username,
        "status": account.status,
        "scopes": account.scopes,
        "expires_at": account.expires_at,
    }


@router.get("/social-accounts")
async def accounts(db: Db, workspace: CurrentWorkspace):
    rows = await db.scalars(select(SocialAccount).where(SocialAccount.workspace_id == workspace.id))
    return [public_account(row) for row in rows]


@router.get("/social-accounts/{platform}/connect")
async def connect(platform: str, db: Db, user: CurrentUser, workspace: CurrentWorkspace):
    if platform != "tiktok":
        raise HTTPException(503, "Instagram connection awaits official specification verification")
    settings = get_settings()
    if not settings.tiktok_client_key or not settings.tiktok_client_secret:
        raise HTTPException(503, "TikTok OAuth is not configured")
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = (
        __import__("base64")
        .urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    db.add(
        OAuthState(
            workspace_id=workspace.id,
            user_id=user.id,
            platform=platform,
            digest=hashlib.sha256(state.encode()).hexdigest(),
            verifier=encrypt(verifier),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )
    )
    scopes = ["user.info.basic", "video.upload"]
    if settings.tiktok_direct_post_enabled:
        scopes.append("video.publish")
    query = urlencode(
        {
            "client_key": settings.tiktok_client_key,
            "response_type": "code",
            "scope": ",".join(scopes),
            "redirect_uri": f"{settings.api_url}/api/v1/oauth/tiktok/callback",
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    return {"url": f"https://www.tiktok.com/v2/auth/authorize/?{query}"}


@router.get("/oauth/{platform}/callback")
async def callback(platform: str, state: str, db: Db, code: str = "", error: str = ""):
    if platform != "tiktok":
        raise HTTPException(404, "Unknown OAuth provider")
    row = (
        await db.execute(
            update(OAuthState)
            .where(
                OAuthState.digest == hashlib.sha256(state.encode()).hexdigest(),
                OAuthState.platform == platform,
                OAuthState.consumed_at.is_(None),
                OAuthState.expires_at > datetime.now(UTC),
            )
            .values(consumed_at=datetime.now(UTC))
            .returning(OAuthState)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(400, "OAuth state expired or already used")
    # Consume before contacting the provider, including when the exchange fails.
    await db.commit()
    settings = get_settings()
    if error or not code:
        return RedirectResponse(
            f"{settings.frontend_url}/accounts?connection=denied", status_code=303
        )
    from app.core.crypto import decrypt

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            data = await tiktok.token_request(
                client,
                {
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": f"{settings.api_url}/api/v1/oauth/tiktok/callback",
                    "code_verifier": decrypt(row.verifier),
                },
            )
            response = await client.get(
                "https://open.tiktokapis.com/v2/user/info/",
                params={"fields": "open_id,display_name"},
                headers={"Authorization": f"Bearer {data['access_token']}"},
            )
            response.raise_for_status()
            profile = response.json()["data"]["user"]
        account = await db.scalar(
            select(SocialAccount)
            .where(
                SocialAccount.workspace_id == row.workspace_id,
                SocialAccount.platform == platform,
                SocialAccount.external_id == data["open_id"],
            )
            .with_for_update()
        )
        if account is None:
            account = SocialAccount(
                workspace_id=row.workspace_id,
                platform=platform,
                external_id=data["open_id"],
                username=profile["display_name"],
            )
            db.add(account)
        account.access_token = encrypt(data["access_token"])
        account.refresh_token = encrypt(data["refresh_token"])
        account.expires_at = datetime.now(UTC) + timedelta(seconds=data["expires_in"])
        account.scopes = data.get("scope", "").split(",")
        account.status = "connected"
        await db.commit()
    except (tiktok.PlatformError, httpx.HTTPError, KeyError, ValueError) as exc:
        raise HTTPException(502, "Could not connect TikTok; start the connection again") from exc
    return RedirectResponse(f"{settings.frontend_url}/accounts?connection=success", status_code=303)


@router.get("/social-accounts/{account_id}/creator-info")
async def creator(account_id: uuid.UUID, db: Db, workspace: CurrentWorkspace):
    account = await db.scalar(
        select(SocialAccount)
        .where(SocialAccount.id == account_id, SocialAccount.workspace_id == workspace.id)
        .with_for_update()
    )
    if account is None:
        raise HTTPException(404, "Account not found")
    if account.platform != "tiktok":
        raise HTTPException(422, "Creator information is available for TikTok")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            token = await access_token(account, client)
            return await tiktok.creator_info(client, token)
    except tiktok.PlatformError as exc:
        await db.commit()
        raise HTTPException(502, exc.code) from exc


@router.delete("/social-accounts/{account_id}", status_code=204)
async def disconnect(account_id: uuid.UUID, db: Db, user: CurrentUser, workspace: CurrentWorkspace):
    account = await db.scalar(
        select(SocialAccount)
        .where(SocialAccount.id == account_id, SocialAccount.workspace_id == workspace.id)
        .with_for_update()
    )
    if account is None:
        raise HTTPException(404, "Account not found")
    active = await db.scalar(
        select(PostTarget.id)
        .join(Post)
        .where(
            PostTarget.account_id == account.id, PostTarget.status.in_(["processing", "uncertain"])
        )
        .limit(1)
    )
    if active:
        raise HTTPException(409, "Resolve active publishing jobs before disconnecting")
    if account.status == "connected" and account.platform == "tiktok":
        from app.core.crypto import decrypt

        async with httpx.AsyncClient(timeout=15) as client:
            try:
                response = await client.post(
                    "https://open.tiktokapis.com/v2/oauth/revoke/",
                    data={
                        "client_key": get_settings().tiktok_client_key,
                        "client_secret": get_settings().tiktok_client_secret,
                        "token": decrypt(account.access_token),
                    },
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise HTTPException(502, "Token revocation failed; retry disconnection") from exc
    await db.execute(
        update(PostTarget)
        .where(
            PostTarget.account_id == account.id,
            PostTarget.status.in_(["scheduled", "queued", "retry"]),
        )
        .values(status="cancelled")
    )
    account.status = "disconnected"
    account.access_token = ""
    account.refresh_token = None
    db.add(
        AuditLog(
            workspace_id=workspace.id,
            user_id=user.id,
            action="account.disconnected",
            resource_id=str(account.id),
        )
    )
