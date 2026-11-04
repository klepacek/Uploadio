import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import httpx
from celery import Celery
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.integrations import instagram, tiktok
from app.models.entities import MediaAsset, Post, PostTarget, PublishAttempt, SocialAccount
from app.services.accounts import access_token, utc
from app.services.storage import media_url, storage

settings = get_settings()
celery_app = Celery("uploadio", broker=settings.redis_url)
celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={"dispatch-due": {"task": "uploadio.dispatch", "schedule": 15.0}},
)


def sessions():
    # A Celery process creates a fresh event loop per task.
    return async_sessionmaker(
        create_async_engine(settings.database_url, poolclass=NullPool), expire_on_commit=False
    )


async def claim_due(db, at: datetime) -> list[uuid.UUID]:
    rows = list(
        await db.scalars(
            select(PostTarget)
            .where(PostTarget.status.in_(["scheduled", "retry"]), PostTarget.scheduled_at <= at)
            .order_by(PostTarget.scheduled_at)
            .with_for_update(skip_locked=True)
            .limit(100)
        )
    )
    for row in rows:
        row.status = "queued"
        row.lease_until = at + timedelta(minutes=2)
    await db.commit()
    return [row.id for row in rows]


async def dispatch_due(factory=None):
    factory = factory or sessions()
    at = datetime.now(UTC)
    async with factory() as db:
        await db.execute(
            update(PostTarget)
            .where(PostTarget.status == "queued", PostTarget.lease_until < at)
            .values(status="retry", scheduled_at=at)
        )
        expired = list(
            await db.scalars(
                select(PostTarget)
                .where(PostTarget.status == "processing", PostTarget.lease_until < at)
                .with_for_update(skip_locked=True)
            )
        )
        reconcile_ids = []
        for target in expired:
            if target.container_id:
                reconcile_ids.append(target.id)
                target.lease_until = at + timedelta(minutes=5)
            else:
                target.status = "uncertain"
                target.error = "Worker interrupted during submission; review before retrying"
        await db.commit()
        ids = await claim_due(db, at)
    for target_id in ids:
        publish_target.apply_async(args=[str(target_id)], task_id=str(target_id))
    for target_id in reconcile_ids:
        reconcile_target.delay(str(target_id))


async def claim_target(db, target_id: uuid.UUID) -> PostTarget | None:
    target = (
        await db.execute(
            update(PostTarget)
            .where(PostTarget.id == target_id, PostTarget.status == "queued")
            .values(
                status="processing",
                lease_until=datetime.now(UTC) + timedelta(minutes=15),
                attempts=PostTarget.attempts + 1,
            )
            .returning(PostTarget)
        )
    ).scalar_one_or_none()
    if target:
        db.add(PublishAttempt(target_id=target.id, number=target.attempts, status="processing"))
        await db.commit()
    return target


def trusted_upload_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return (
        parsed.scheme == "https"
        and parsed.port in (None, 443)
        and not parsed.username
        and not parsed.password
        and (host == "tiktokapis.com" or host.endswith(".tiktokapis.com"))
    )


async def upload_binary(client: httpx.AsyncClient, url: str, media: MediaAsset):
    if not trusted_upload_url(url):
        raise tiktok.PlatformError("unsafe_upload_url")
    response = await asyncio.to_thread(
        storage().get_object, Bucket=settings.r2_bucket, Key=media.object_key
    )
    body = response["Body"]
    chunk_size = min(media.size_bytes, 10_000_000)
    count = max(1, media.size_bytes // chunk_size)
    offset = 0
    try:
        for index in range(count):
            length = media.size_bytes - offset if index == count - 1 else chunk_size
            chunk = await asyncio.to_thread(body.read, length)
            if len(chunk) != length:
                raise tiktok.PlatformError("incomplete_stored_media")
            result = await client.put(
                url,
                content=chunk,
                headers={
                    "Content-Type": media.content_type,
                    "Content-Length": str(length),
                    "Content-Range": f"bytes {offset}-{offset + length - 1}/{media.size_bytes}",
                },
            )
            if result.status_code not in (201, 206):
                raise tiktok.PlatformError("video_transfer_failed", uncertain=True)
            offset += length
    finally:
        body.close()


async def finish_attempt(db, target: PostTarget):
    attempt = await db.scalar(
        select(PublishAttempt).where(
            PublishAttempt.target_id == target.id, PublishAttempt.number == target.attempts
        )
    )
    if attempt:
        attempt.status, attempt.error = target.status, target.error


async def run_target(target_id: uuid.UUID, factory=None):
    factory = factory or sessions()
    async with factory() as db:
        target = await claim_target(db, target_id)
        if target is None:
            return
        account = await db.scalar(
            select(SocialAccount).where(SocialAccount.id == target.account_id).with_for_update()
        )
        post = await db.get(Post, target.post_id)
        media = await db.get(MediaAsset, post.media_id)
        try:
            async with httpx.AsyncClient(timeout=120, follow_redirects=False) as client:
                token = await access_token(account, client)
                await db.commit()
                if account.platform == "instagram":
                    target.container_id = await instagram.create_container(
                        client,
                        token,
                        account.external_id,
                        target.format,
                        media_url(media.object_key),
                        target.caption or post.caption,
                    )
                    target.lease_until = datetime.now(UTC) + timedelta(minutes=1)
                    await db.commit()
                    return
                data = await tiktok.initialize(
                    client,
                    token,
                    media.size_bytes,
                    target.caption or post.caption,
                    target.settings,
                    target.format == "tiktok_direct",
                    bool(target.consent_at),
                    media.metadata_["duration"],
                )
                target.container_id = data["publish_id"]
                await db.commit()
                await upload_binary(client, data["upload_url"], media)
                target.lease_until = datetime.now(UTC) + timedelta(seconds=30)
                await db.commit()
        except tiktok.PlatformError as exc:
            target.error = exc.code
            if target.container_id or exc.uncertain:
                target.status = "processing" if target.container_id else "uncertain"
                target.lease_until = datetime.now(UTC) + timedelta(minutes=1)
            elif exc.retryable and target.attempts < 5:
                target.status = "retry"
                target.scheduled_at = datetime.now(UTC) + timedelta(seconds=30 * 2**target.attempts)
            else:
                target.status = "failed"
            await finish_attempt(db, target)
            await db.commit()
        except Exception:
            # Unknown outcomes require reconciliation, never a new submission.
            target.status = "processing" if target.container_id else "uncertain"
            target.error = "Publishing interrupted; outcome requires reconciliation"
            target.lease_until = datetime.now(UTC) + timedelta(minutes=1)
            await finish_attempt(db, target)
            await db.commit()


async def reconcile(target_id: uuid.UUID, factory=None):
    factory = factory or sessions()
    async with factory() as db:
        target = await db.scalar(
            select(PostTarget)
            .where(PostTarget.id == target_id, PostTarget.status == "processing")
            .with_for_update(skip_locked=True)
        )
        if target is None or not target.container_id:
            return
        account = await db.scalar(
            select(SocialAccount).where(SocialAccount.id == target.account_id).with_for_update()
        )
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                token = await access_token(account, client)
                if account.platform == "instagram":
                    await reconcile_instagram(db, target, account, token, client)
                    await finish_attempt(db, target)
                    await db.commit()
                    return
                data = await tiktok.status(client, token, target.container_id)
            state = data["status"]
            if state == "PUBLISH_COMPLETE":
                target.status = "published"
                target.published_at = datetime.now(UTC)
                ids = data.get("publicaly_available_post_id", [])
                if ids:
                    target.external_id = str(ids[0])

                target.error = None
            elif state == "SEND_TO_USER_INBOX":
                target.status = "draft_uploaded"
                target.error = None
            elif state == "FAILED":
                target.status = "failed"
                target.error = str(data.get("fail_reason", "platform_rejected"))[:500]
            else:
                target.lease_until = datetime.now(UTC) + timedelta(minutes=1)
        except (tiktok.PlatformError, httpx.HTTPError, KeyError):
            target.error = "Status check unavailable; reconciliation will retry"
            target.lease_until = datetime.now(UTC) + timedelta(minutes=5)
        await finish_attempt(db, target)
        await db.commit()


async def reconcile_instagram(db, target, account, token, client):
    state = await instagram.container_status(client, token, target.container_id)
    if state == "PUBLISHED":
        target.status = "published"
        target.published_at = target.published_at or datetime.now(UTC)
        target.error = None
    elif state in {"ERROR", "EXPIRED"}:
        target.status = "failed"
        target.error = f"Instagram container {state.lower()}"
    elif state == "FINISHED" and target.publish_submitted_at is None:
        target.publish_submitted_at = datetime.now(UTC)
        await db.commit()
        target.external_id = await instagram.publish(
            client, token, account.external_id, target.container_id
        )
        target.status = "published"
        target.published_at = datetime.now(UTC)
        target.error = None
        await db.commit()
        try:
            result = await instagram.request(
                client, "GET", target.external_id, token, {"fields": "permalink"}
            )
            target.external_url = result.get("permalink")
        except tiktok.PlatformError:
            pass
    elif target.publish_submitted_at and (
        datetime.now(UTC) - utc(target.publish_submitted_at)
    ) > timedelta(minutes=5):
        target.status = "uncertain"
        target.error = "Instagram did not confirm submission; review the account before retrying"
    else:
        target.lease_until = datetime.now(UTC) + timedelta(minutes=1)


@celery_app.task(name="uploadio.dispatch")
def dispatch_task():
    asyncio.run(dispatch_due())


@celery_app.task(name="uploadio.publish")
def publish_target(target_id: str):
    asyncio.run(run_target(uuid.UUID(target_id)))


@celery_app.task(name="uploadio.reconcile")
def reconcile_target(target_id: str):
    asyncio.run(reconcile(uuid.UUID(target_id)))
