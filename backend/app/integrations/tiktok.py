import httpx

from app.core.config import get_settings

BASE = "https://open.tiktokapis.com/v2"


class PlatformError(Exception):
    def __init__(self, code: str, retryable: bool = False, uncertain: bool = False):
        self.code = code[:100]
        self.retryable = retryable
        self.uncertain = uncertain
        super().__init__(self.code)


async def request(client: httpx.AsyncClient, path: str, token: str, data: dict) -> dict:
    try:
        response = await client.post(
            f"{BASE}/{path}/", json=data, headers={"Authorization": f"Bearer {token}"}
        )
    except httpx.HTTPError as exc:
        raise PlatformError("network_error", uncertain=True) from exc
    if response.status_code == 429:
        raise PlatformError("rate_limit_exceeded", retryable=True)
    if response.status_code >= 500:
        raise PlatformError("platform_unavailable", uncertain=True)
    try:
        body = response.json()
    except ValueError as exc:
        raise PlatformError("invalid_platform_response", uncertain=True) from exc
    error = body.get("error", {})
    if response.is_error or error.get("code", "ok") != "ok":
        raise PlatformError(str(error.get("code", "platform_error")))
    return body.get("data", {})


async def creator_info(client: httpx.AsyncClient, token: str) -> dict:
    return await request(client, "post/publish/creator_info/query", token, {})


async def initialize(
    client: httpx.AsyncClient,
    token: str,
    size: int,
    caption: str,
    settings: dict,
    direct: bool,
    consent: bool,
    duration: float,
) -> dict:
    if not consent:
        raise PlatformError("explicit_consent_required")
    source = {
        "source": "FILE_UPLOAD",
        "video_size": size,
        "chunk_size": min(size, 10_000_000),
        "total_chunk_count": max(1, size // 10_000_000),
    }
    if not direct:
        if not 0 < duration <= 600:
            raise PlatformError("draft_duration_limit")
        return await request(
            client, "post/publish/inbox/video/init", token, {"source_info": source}
        )
    if not get_settings().tiktok_direct_post_enabled:
        raise PlatformError("direct_post_approval_required")
    info = await creator_info(client, token)
    if duration > info.get("max_video_post_duration_sec", 0):
        raise PlatformError("creator_duration_limit")
    privacy = settings.get("privacy_level")
    if privacy not in info.get("privacy_level_options", []):
        raise PlatformError("invalid_privacy_level")
    for interaction in ("comment", "duet", "stitch"):
        if info.get(f"{interaction}_disabled") and not settings.get(f"disable_{interaction}", True):
            raise PlatformError(f"{interaction}_disabled")
    post_info = {
        "title": caption,
        "privacy_level": privacy,
        "disable_comment": settings.get("disable_comment", True),
        "disable_duet": settings.get("disable_duet", True),
        "disable_stitch": settings.get("disable_stitch", True),
        "brand_content_toggle": settings.get("brand_content_toggle", False),
        "brand_organic_toggle": settings.get("brand_organic_toggle", False),
    }
    return await request(
        client, "post/publish/video/init", token, {"source_info": source, "post_info": post_info}
    )


async def status(client: httpx.AsyncClient, token: str, publish_id: str) -> dict:
    return await request(client, "post/publish/status/fetch", token, {"publish_id": publish_id})


async def token_request(client: httpx.AsyncClient, data: dict) -> dict:
    settings = get_settings()
    response = await client.post(
        f"{BASE}/oauth/token/",
        data={
            "client_key": settings.tiktok_client_key,
            "client_secret": settings.tiktok_client_secret,
            **data,
        },
    )
    if response.is_error:
        raise PlatformError("token_exchange_failed")
    body = response.json()
    if "access_token" not in body:
        raise PlatformError("token_exchange_failed")
    return body
