from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest
from cryptography.fernet import Fernet

from app.core.config import get_settings
from app.core.crypto import decrypt, encrypt
from app.integrations import instagram
from app.integrations.tiktok import PlatformError
from app.models.entities import SocialAccount
from app.services.accounts import access_token
from app.workers.tasks import reconcile_instagram


async def test_reel_and_story_payloads(respx_mock):
    route = respx_mock.post(f"{instagram.base()}/123/media").mock(
        return_value=httpx.Response(200, json={"id": "container"})
    )
    async with httpx.AsyncClient() as client:
        assert (
            await instagram.create_container(
                client, "token", "123", "reel", "https://media.test/video", "Caption"
            )
            == "container"
        )
        import json

        assert json.loads(route.calls.last.request.content)["media_type"] == "REELS"
        await instagram.create_container(
            client, "token", "123", "story", "https://media.test/video", "ignored"
        )
        payload = json.loads(route.calls.last.request.content)
        assert payload["media_type"] == "STORIES" and "caption" not in payload


async def test_ambiguous_publish_is_not_retried(respx_mock):
    from types import SimpleNamespace

    target = SimpleNamespace(
        container_id="container",
        publish_submitted_at=None,
        status="processing",
        external_id=None,
        published_at=None,
        error=None,
    )
    account = SimpleNamespace(external_id="123")
    db = AsyncMock()
    respx_mock.get(f"{instagram.base()}/container").mock(
        return_value=httpx.Response(200, json={"status_code": "FINISHED"})
    )
    publish = respx_mock.post(f"{instagram.base()}/123/media_publish").mock(
        side_effect=httpx.ReadTimeout("ambiguous")
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(PlatformError):
            await reconcile_instagram(db, target, account, "token", client)
        assert target.publish_submitted_at is not None
        await reconcile_instagram(db, target, account, "token", client)
        assert publish.call_count == 1
        respx_mock.get(f"{instagram.base()}/container").mock(
            return_value=httpx.Response(200, json={"status_code": "PUBLISHED"})
        )
        await reconcile_instagram(db, target, account, "token", client)
        assert target.status == "published"


async def test_instagram_refresh(respx_mock, monkeypatch):
    monkeypatch.setattr(get_settings(), "token_encryption_key", Fernet.generate_key().decode())
    account = SocialAccount(
        platform="instagram",
        status="connected",
        access_token=encrypt("old"),
        expires_at=datetime.now(UTC) + timedelta(minutes=1),
    )
    respx_mock.get("https://graph.instagram.com/refresh_access_token").mock(
        return_value=httpx.Response(200, json={"access_token": "new", "expires_in": 5184000})
    )
    async with httpx.AsyncClient() as client:
        assert await access_token(account, client) == "new"
    assert decrypt(account.access_token) == "new"


async def test_instagram_state_replay(client, monkeypatch):
    from urllib.parse import parse_qs, urlparse

    monkeypatch.setattr(get_settings(), "instagram_app_id", "test")
    monkeypatch.setattr(get_settings(), "instagram_app_secret", "test")
    monkeypatch.setattr(get_settings(), "token_encryption_key", Fernet.generate_key().decode())
    result = (await client.get("/api/v1/social-accounts/instagram/connect")).json()
    state = parse_qs(urlparse(result["url"]).query)["state"][0]
    params = {"state": state, "error": "denied"}
    assert (await client.get("/api/v1/oauth/instagram/callback", params=params)).status_code == 303
    assert (await client.get("/api/v1/oauth/instagram/callback", params=params)).status_code == 400
