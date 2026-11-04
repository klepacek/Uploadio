import uuid

import pytest

from app.services.media import InvalidMedia, validate_probe


def probe(**values):
    return {
        "format": {"duration": "25", "format_name": "mov,mp4"},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "avg_frame_rate": "30/1",
                "width": 1080,
                "height": 1920,
                **values,
            }
        ],
    }


def test_video_validation():
    assert validate_probe(probe())["width"] == 1080
    for data in [probe(codec_name="vp9"), probe(width=9000), {"streams": []}]:
        with pytest.raises(InvalidMedia):
            validate_probe(data)


async def test_upload_validation(client):
    response = await client.post(
        "/api/v1/media/upload-url",
        json={"filename": "../secret.mp4", "content_type": "video/mp4", "size_bytes": 12},
    )
    assert response.status_code == 422
    response = await client.post(
        "/api/v1/media/upload-url",
        json={"filename": "video.mp4", "content_type": "video/mp4", "size_bytes": 600_000_000},
    )
    assert response.status_code == 422


async def test_media_isolation(client):
    response = await client.post("/api/v1/media/complete", json={"media_id": str(uuid.uuid4())})
    assert response.status_code == 404


async def test_upload_completion_and_quota(client, monkeypatch):
    from unittest.mock import Mock

    from app.api import media
    from app.core.config import get_settings

    fake = Mock()
    fake.generate_presigned_url.return_value = "https://storage.example/upload"
    monkeypatch.setattr(media, "storage", lambda: fake)
    monkeypatch.setattr(
        media,
        "inspect_upload",
        lambda key, size: ({"width": 1080, "height": 1920, "duration": 30}, f"{key}.jpg"),
    )
    payload = {"filename": "clip.mp4", "content_type": "video/mp4", "size_bytes": 100}
    response = await client.post("/api/v1/media/upload-url", json=payload)
    assert response.status_code == 201
    media_id = response.json()["media_id"]
    response = await client.post("/api/v1/media/complete", json={"media_id": media_id})
    assert response.json()["status"] == "ready"
    monkeypatch.setattr(get_settings(), "workspace_quota_bytes", 150)
    response = await client.post("/api/v1/media/upload-url", json=payload)
    assert response.status_code == 409
