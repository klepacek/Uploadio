import httpx

from app.core.config import get_settings
from app.integrations.tiktok import PlatformError


def base() -> str:
    return f"https://graph.instagram.com/{get_settings().instagram_api_version}"


async def request(
    client: httpx.AsyncClient, method: str, path: str, token: str, data: dict | None = None
) -> dict:
    try:
        response = await client.request(
            method,
            f"{base()}/{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=data if method == "GET" else None,
            json=data if method != "GET" else None,
        )
    except httpx.HTTPError as exc:
        raise PlatformError(
            "instagram_network_error", uncertain=method == "POST", retryable=method == "GET"
        ) from exc
    if response.status_code == 429:
        raise PlatformError("instagram_rate_limit", retryable=True)
    if response.status_code >= 500:
        raise PlatformError(
            "instagram_unavailable", uncertain=method == "POST", retryable=method == "GET"
        )
    body = response.json()
    if response.is_error or "error" in body:
        code = str(body.get("error", {}).get("code", "request_failed"))
        raise PlatformError(f"instagram_{code}", retryable=code in {"4", "17", "32", "613"})
    return body


async def create_container(
    client: httpx.AsyncClient,
    token: str,
    account_id: str,
    format: str,
    video_url: str,
    caption: str,
) -> str:
    payload = {"media_type": "STORIES" if format == "story" else "REELS", "video_url": video_url}
    if format == "reel":
        payload["caption"] = caption
    data = await request(client, "POST", f"{account_id}/media", token, payload)
    return str(data["id"])


async def container_status(client: httpx.AsyncClient, token: str, container_id: str) -> str:
    data = await request(client, "GET", container_id, token, {"fields": "status_code"})
    return data["status_code"]


async def publish(client: httpx.AsyncClient, token: str, account_id: str, container_id: str) -> str:
    data = await request(
        client, "POST", f"{account_id}/media_publish", token, {"creation_id": container_id}
    )
    return str(data["id"])


async def refresh(client: httpx.AsyncClient, token: str) -> dict:
    response = await client.get(
        "https://graph.instagram.com/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": token},
    )
    if response.is_error or "access_token" not in response.json():
        raise PlatformError("instagram_refresh_failed")
    return response.json()


async def exchange(client: httpx.AsyncClient, code: str, redirect: str) -> tuple[dict, list[str]]:
    settings = get_settings()
    response = await client.post(
        "https://api.instagram.com/oauth/access_token",
        data={
            "client_id": settings.instagram_app_id,
            "client_secret": settings.instagram_app_secret,
            "grant_type": "authorization_code",
            "redirect_uri": redirect,
            "code": code,
        },
    )
    if response.is_error:
        raise PlatformError("instagram_token_exchange_failed")
    body = response.json()
    short = body["data"][0] if "data" in body else body
    scopes = short.get("permissions", "").split(",")
    response = await client.get(
        "https://graph.instagram.com/access_token",
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": settings.instagram_app_secret,
            "access_token": short["access_token"],
        },
    )
    if response.is_error or "access_token" not in response.json():
        raise PlatformError("instagram_token_exchange_failed")
    return response.json(), scopes
