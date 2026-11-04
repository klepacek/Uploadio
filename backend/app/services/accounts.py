from datetime import UTC, datetime, timedelta

import httpx

from app.core.crypto import decrypt, encrypt
from app.integrations.tiktok import PlatformError, token_request
from app.models.entities import SocialAccount


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def access_token(account: SocialAccount, client: httpx.AsyncClient) -> str:
    if account.status != "connected":
        raise PlatformError("account_disconnected")
    if account.expires_at and utc(account.expires_at) <= datetime.now(UTC) + timedelta(minutes=5):
        if account.platform == "instagram":
            from app.integrations import instagram

            if utc(account.expires_at) <= datetime.now(UTC):
                account.status = "expired"
                raise PlatformError("reconnect_account")
            data = await instagram.refresh(client, decrypt(account.access_token))
            account.access_token = encrypt(data["access_token"])
            account.expires_at = datetime.now(UTC) + timedelta(seconds=data["expires_in"])
            return data["access_token"]
        if not account.refresh_token:
            account.status = "expired"
            raise PlatformError("reconnect_account")
        try:
            data = await token_request(
                client,
                {"grant_type": "refresh_token", "refresh_token": decrypt(account.refresh_token)},
            )
        except PlatformError:
            account.status = "expired"
            raise
        account.access_token = encrypt(data["access_token"])
        account.refresh_token = encrypt(data["refresh_token"])
        account.expires_at = datetime.now(UTC) + timedelta(seconds=data["expires_in"])
    return decrypt(account.access_token)
