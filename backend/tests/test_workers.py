from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.integrations.tiktok import PlatformError
from app.models.entities import PostTarget
from app.workers import tasks


async def setup_target(client, post_payload, db):
    post_id = (await client.post("/api/v1/posts", json=post_payload)).json()["id"]
    await client.post(f"/api/v1/posts/{post_id}/publish", json={"consent": True})
    return (await tasks.claim_due(db, datetime.now(UTC)))[0]


def factory(db):
    @asynccontextmanager
    async def session():
        yield db

    return session


@pytest.mark.parametrize(
    "outcome,expected",
    [("rate_limit", "retry"), ("timeout", "uncertain"), ("permission", "failed")],
)
async def test_retry_policy(client, post_payload, db, monkeypatch, outcome, expected):
    target_id = await setup_target(client, post_payload, db)

    async def token(*args):
        return "token"

    async def initialize(*args):
        raise PlatformError(
            outcome, retryable=outcome == "rate_limit", uncertain=outcome == "timeout"
        )

    monkeypatch.setattr(tasks, "access_token", token)
    monkeypatch.setattr(tasks.tiktok, "initialize", initialize)
    await tasks.run_target(target_id, factory(db))
    target = await db.get(PostTarget, target_id)
    assert target.status == expected
    if expected == "retry":
        assert target.scheduled_at.replace(tzinfo=UTC) > datetime.now(UTC)
    assert await tasks.claim_target(db, target_id) is None


@pytest.mark.parametrize(
    "state,expected",
    [
        ("SEND_TO_USER_INBOX", "draft_uploaded"),
        ("PUBLISH_COMPLETE", "published"),
        ("FAILED", "failed"),
    ],
)
async def test_reconciliation(client, post_payload, db, monkeypatch, state, expected):
    target_id = await setup_target(client, post_payload, db)
    target = await tasks.claim_target(db, target_id)
    target.container_id = "publish-123"
    await db.commit()

    async def token(*args):
        return "token"

    async def status(*args):
        return {"status": state, "fail_reason": "rejected"}

    monkeypatch.setattr(tasks, "access_token", token)
    monkeypatch.setattr(tasks.tiktok, "status", status)
    await tasks.reconcile(target_id, factory(db))
    assert target.status == expected
    assert bool(target.published_at) == (expected == "published")


async def test_partial_success(client, post_payload, db):

    from app.models.entities import SocialAccount

    original = await db.scalar(select(SocialAccount))
    other = SocialAccount(
        workspace_id=original.workspace_id,
        platform="tiktok",
        external_id="other",
        username="second",
        access_token="encrypted",
        scopes=["video.upload"],
    )
    db.add(other)
    await db.commit()
    post_payload["targets"].append({"account_id": str(other.id), "format": "tiktok_draft"})
    post = (await client.post("/api/v1/posts", json=post_payload)).json()
    targets = list(await db.scalars(select(PostTarget)))
    targets[0].status, targets[1].status = "published", "failed"
    targets[0].published_at = datetime.now(UTC)
    await db.commit()
    data = (await client.get(f"/api/v1/posts/{post['id']}")).json()
    assert {t["status"] for t in data["targets"]} == {"published", "failed"}


async def test_interrupted_job_recovery(client, post_payload, db, monkeypatch):
    from datetime import timedelta
    from unittest.mock import Mock

    target_id = await setup_target(client, post_payload, db)
    target = await db.get(PostTarget, target_id)
    send = Mock()
    poll = Mock()
    monkeypatch.setattr(tasks.publish_target, "apply_async", send)
    monkeypatch.setattr(tasks.reconcile_target, "delay", poll)
    target.lease_until = datetime.now(UTC) - timedelta(minutes=1)
    await db.commit()
    await tasks.dispatch_due(factory(db))
    assert send.call_count == 1
    assert target.status == "queued"
    send.reset_mock()
    target.status = "processing"
    target.lease_until = datetime.now(UTC) - timedelta(minutes=1)
    await db.commit()
    await tasks.dispatch_due(factory(db))
    assert target.status == "uncertain"
    send.assert_not_called()
    target.status = "processing"
    target.container_id = "existing-provider-job"
    target.lease_until = datetime.now(UTC) - timedelta(minutes=1)
    await db.commit()
    await tasks.dispatch_due(factory(db))
    poll.assert_called_once_with(str(target_id))
    send.assert_not_called()
