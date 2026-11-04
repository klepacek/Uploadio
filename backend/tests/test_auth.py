import uuid

import httpx
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.auth import current_user
from app.core.config import get_settings


async def test_auth_required(db):
    with pytest.raises(HTTPException) as error:
        await current_user(db, None)
    assert error.value.status_code == 401


async def test_me_and_workspace_isolation(client):
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 200
    assert response.json()["email"] == "owner@example.com"
    response = await client.get("/api/v1/users/me", headers={"X-Workspace-ID": str(uuid.uuid4())})
    assert response.status_code == 404


async def test_profile_validation(client):
    response = await client.patch(
        "/api/v1/users/me", json={"display_name": "Vojtěch", "timezone": "Europe/Prague"}
    )
    assert response.status_code == 200
    response = await client.patch(
        "/api/v1/users/me", json={"display_name": "Vojtěch", "timezone": "invalid"}
    )
    assert response.status_code == 422


async def test_supabase_rejects_invalid_token(db, respx_mock, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "supabase_url", "https://auth.example.com")
    monkeypatch.setattr(settings, "supabase_publishable_key", "public-test-key")
    respx_mock.get("https://auth.example.com/auth/v1/user").mock(return_value=httpx.Response(401))
    with pytest.raises(HTTPException) as error:
        await current_user(db, HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid"))
    assert error.value.status_code == 401
