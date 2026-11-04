from unittest.mock import AsyncMock

from app.core.config import get_settings


async def test_rate_limit(client, monkeypatch):
    from app.core import middleware

    monkeypatch.setattr(get_settings(), "rate_limit_enabled", True)
    redis = AsyncMock()
    redis.__aenter__.return_value = redis
    redis.eval.return_value = 121
    monkeypatch.setattr(middleware.Redis, "from_url", lambda *a, **kw: redis)
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"


async def test_sensitive_responses_not_cached(client):
    response = await client.get("/api/v1/users/me")
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


async def test_account_response_never_exposes_tokens(client, db, post_payload):
    response = await client.get("/api/v1/social-accounts")
    data = response.json()[0]
    assert "access_token" not in data and "refresh_token" not in data
