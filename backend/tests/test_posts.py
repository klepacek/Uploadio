import uuid
from datetime import UTC, datetime, timedelta

from app.workers.tasks import claim_due, claim_target, trusted_upload_url


async def test_create_edit_and_isolation(client, post_payload):
    response = await client.post("/api/v1/posts", json=post_payload)
    assert response.status_code == 201
    post_id = response.json()["id"]
    post_payload["caption"] = "Updated"
    response = await client.patch(f"/api/v1/posts/{post_id}", json=post_payload)
    assert response.json()["caption"] == "Updated"
    response = await client.get(
        f"/api/v1/posts/{post_id}", headers={"X-Workspace-ID": str(uuid.uuid4())}
    )
    assert response.status_code == 404


async def test_schedule_claim_and_duplicate_protection(client, post_payload, db):
    response = await client.post("/api/v1/posts", json=post_payload)
    post_id = response.json()["id"]
    response = await client.post(f"/api/v1/posts/{post_id}/publish", json={"consent": False})
    assert response.status_code == 422
    response = await client.post(f"/api/v1/posts/{post_id}/publish", json={"consent": True})
    assert response.json()["targets"][0]["status"] == "scheduled"
    response = await client.post(f"/api/v1/posts/{post_id}/publish", json={"consent": True})
    assert response.status_code == 409
    ids = await claim_due(db, datetime.now(UTC) + timedelta(seconds=1))
    assert len(ids) == 1
    assert await claim_due(db, datetime.now(UTC) + timedelta(seconds=1)) == []
    assert await claim_target(db, ids[0]) is not None
    assert await claim_target(db, ids[0]) is None
    response = await client.post(f"/api/v1/posts/{post_id}/cancel")
    assert response.status_code == 409


async def test_schedule_cancel(client, post_payload, db):
    post_id = (await client.post("/api/v1/posts", json=post_payload)).json()["id"]
    response = await client.post(
        f"/api/v1/posts/{post_id}/schedule",
        json={"consent": True, "scheduled_at": (datetime.now(UTC) + timedelta(days=1)).isoformat()},
    )
    assert response.status_code == 200
    response = await client.post(f"/api/v1/posts/{post_id}/cancel")
    assert response.json()["targets"][0]["status"] == "cancelled"
    assert await claim_due(db, datetime.now(UTC) + timedelta(days=2)) == []


async def test_media_cannot_be_referenced_from_another_workspace(client, post_payload):
    post_payload["media_id"] = str(uuid.uuid4())
    assert (await client.post("/api/v1/posts", json=post_payload)).status_code == 422


def test_upload_destination_validation():
    assert trusted_upload_url("https://upload.us.tiktokapis.com/video/?token=x")
    for value in [
        "http://upload.us.tiktokapis.com",
        "https://tiktokapis.com.evil.test",
        "https://127.0.0.1",
        "https://user:pass@tiktokapis.com",
    ]:
        assert not trusted_upload_url(value)
