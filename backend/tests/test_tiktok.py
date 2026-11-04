import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from cryptography.fernet import Fernet

from app.core.config import get_settings
from app.core.crypto import decrypt, encrypt
from app.integrations.tiktok import PlatformError, initialize, request
from app.models.entities import SocialAccount
from app.services.accounts import access_token


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    monkeypatch.setattr(get_settings(), "token_encryption_key", Fernet.generate_key().decode())


def test_tokens_encrypted():
    secret = encrypt("oauth-secret")
    assert "oauth-secret" not in secret
    assert decrypt(secret) == "oauth-secret"


async def test_oauth_rejects_state_and_replay(client, monkeypatch, respx_mock):
    monkeypatch.setattr(get_settings(), "tiktok_client_key", "test")
    monkeypatch.setattr(get_settings(), "tiktok_client_secret", "test")
    response = await client.get("/api/v1/social-accounts/tiktok/connect")
    from urllib.parse import parse_qs, urlparse

    params = parse_qs(urlparse(response.json()["url"]).query)
    assert params["code_challenge_method"] == ["S256"]
    state = params["state"][0]
    response = await client.get(
        "/api/v1/oauth/tiktok/callback", params={"state": state, "error": "denied"}
    )
    assert response.status_code == 303
    response = await client.get(
        "/api/v1/oauth/tiktok/callback", params={"state": state, "code": "test"}
    )
    assert response.status_code == 400
    response = await client.get("/api/v1/oauth/tiktok/callback", params={"state": "wrong"})
    assert response.status_code == 400


async def test_refresh_rotates_tokens(respx_mock):
    account = SocialAccount(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        platform="tiktok",
        external_id="123",
        username="creator",
        status="connected",
        access_token=encrypt("old"),
        refresh_token=encrypt("refresh-old"),
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    respx_mock.post("https://open.tiktokapis.com/v2/oauth/token/").mock(
        return_value=httpx.Response(
            200, json={"access_token": "new", "refresh_token": "refresh-new", "expires_in": 7200}
        )
    )
    async with httpx.AsyncClient() as client:
        assert await access_token(account, client) == "new"
    assert decrypt(account.refresh_token) == "refresh-new"


async def test_draft_and_direct_are_separate(respx_mock, monkeypatch):
    respx_mock.post("https://open.tiktokapis.com/v2/post/publish/creator_info/query/").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {"max_video_post_duration_sec": 60, "privacy_level_options": ["SELF_ONLY"]},
                "error": {"code": "ok"},
            },
        )
    )
    inbox = respx_mock.post("https://open.tiktokapis.com/v2/post/publish/inbox/video/init/").mock(
        return_value=httpx.Response(
            200, json={"data": {"publish_id": "draft-1"}, "error": {"code": "ok"}}
        )
    )
    async with httpx.AsyncClient() as client:
        data = await initialize(client, "token", 100, "caption", {}, False, True, 30)
        assert data["publish_id"] == "draft-1"
        assert inbox.called
        with pytest.raises(PlatformError, match="explicit_consent"):
            await initialize(client, "token", 100, "caption", {}, False, False, 30)
        with pytest.raises(PlatformError, match="approval"):
            await initialize(client, "token", 100, "caption", {}, True, True, 30)
        monkeypatch.setattr(get_settings(), "tiktok_direct_post_enabled", True)
        with pytest.raises(PlatformError, match="privacy"):
            await initialize(
                client,
                "token",
                100,
                "caption",
                {"privacy_level": "PUBLIC_TO_EVERYONE"},
                True,
                True,
                30,
            )


async def test_platform_failures(respx_mock):
    route = respx_mock.post("https://open.tiktokapis.com/v2/test/")
    async with httpx.AsyncClient() as client:
        route.mock(return_value=httpx.Response(429))
        with pytest.raises(PlatformError) as error:
            await request(client, "test", "token", {})
        assert error.value.retryable
        route.mock(side_effect=httpx.ReadTimeout("timeout"))
        with pytest.raises(PlatformError) as error:
            await request(client, "test", "token", {})
        assert error.value.uncertain


async def test_inbox_upload_does_not_require_direct_post_scope(respx_mock):
    inbox = respx_mock.post("https://open.tiktokapis.com/v2/post/publish/inbox/video/init/").mock(
        return_value=httpx.Response(
            200, json={"data": {"publish_id": "draft-only"}, "error": {"code": "ok"}}
        )
    )
    async with httpx.AsyncClient() as client:
        result = await initialize(client, "upload-only-token", 100, "", {}, False, True, 30)
    assert inbox.call_count == 1
    assert result["publish_id"] == "draft-only"


async def test_disconnection_does_not_hide_provider_revocation_failure(
    client, db, post_payload, respx_mock
):
    from sqlalchemy import select

    account = await db.scalar(select(SocialAccount))
    account.access_token = encrypt("token")
    await db.commit()
    respx_mock.post("https://open.tiktokapis.com/v2/oauth/revoke/").mock(
        return_value=httpx.Response(200, json={"error": {"code": "internal_error"}})
    )
    response = await client.delete(f"/api/v1/social-accounts/{account.id}")
    assert response.status_code == 502
    assert account.status == "connected"
    assert decrypt(account.access_token) == "token"
