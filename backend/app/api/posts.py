import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.core.auth import CurrentWorkspace, Db
from app.core.config import get_settings
from app.models.entities import MediaAsset, Post, PostTarget, SocialAccount
from app.schemas.posts import DispatchInput, PostInput, PostOutput, ScheduleInput, TargetOutput

router = APIRouter(prefix="/api/v1", tags=["posts"])
EDITABLE = {"draft", "cancelled"}


async def owned_post(post_id: uuid.UUID, db: Db, workspace_id: uuid.UUID) -> Post:
    post = await db.scalar(
        select(Post).where(Post.id == post_id, Post.workspace_id == workspace_id).with_for_update()
    )
    if post is None:
        raise HTTPException(404, "Post not found")
    return post


async def post_targets(db: Db, post_id: uuid.UUID) -> list[PostTarget]:
    return list(
        await db.scalars(select(PostTarget).where(PostTarget.post_id == post_id).with_for_update())
    )


async def output(post: Post, db: Db) -> PostOutput:
    rows = (
        await db.execute(
            select(PostTarget, SocialAccount)
            .join(SocialAccount, PostTarget.account_id == SocialAccount.id)
            .where(PostTarget.post_id == post.id)
        )
    ).all()
    return PostOutput(
        id=post.id,
        media_id=post.media_id,
        caption=post.caption,
        timezone=post.timezone,
        created_at=post.created_at,
        targets=[
            TargetOutput(
                id=t.id,
                account_id=a.id,
                username=a.username,
                platform=a.platform,
                format=t.format,
                caption=t.caption,
                settings=t.settings,
                status=t.status,
                scheduled_at=t.scheduled_at,
                published_at=t.published_at,
                external_url=t.external_url,
                error=t.error,
            )
            for t, a in rows
        ],
    )


async def validate_post(data: PostInput, db: Db, workspace_id: uuid.UUID):
    try:
        data.validate_timezone()
    except ValueError as exc:
        raise HTTPException(422, "Invalid timezone") from exc
    media = await db.scalar(
        select(MediaAsset)
        .where(
            MediaAsset.id == data.media_id,
            MediaAsset.workspace_id == workspace_id,
            MediaAsset.status == "ready",
        )
        .with_for_update()
    )
    if media is None:
        raise HTTPException(422, "Select validated media from this workspace")
    seen = set()
    for target in data.targets:
        key = (target.account_id, target.format)
        if key in seen:
            raise HTTPException(422, "Duplicate account and format")
        seen.add(key)
        account = await db.scalar(
            select(SocialAccount).where(
                SocialAccount.id == target.account_id, SocialAccount.workspace_id == workspace_id
            )
        )
        if account is None or account.status != "connected":
            raise HTTPException(422, "Selected account is unavailable")
        if account.platform == "instagram":
            if target.format not in {"reel", "story"}:
                raise HTTPException(422, "Choose an Instagram publishing format")
            if "instagram_business_content_publish" not in account.scopes:
                raise HTTPException(422, "Instagram publishing permission is missing")
            if target.format == "story" and account.details.get("account_type") != "BUSINESS":
                raise HTTPException(422, "Stories require an eligible Instagram business account")
            meta = media.metadata_
            max_size = 100_000_000 if target.format == "story" else 300_000_000
            ratio = meta.get("width", 1) / max(1, meta.get("height", 1))
            if media.size_bytes > max_size or meta.get("width", 0) > 1920:
                raise HTTPException(422, "Instagram video exceeds file size or 1920px width limit")
            if not (0.1 if target.format == "story" else 0.01) <= ratio <= 10:
                raise HTTPException(422, "Instagram does not support this aspect ratio")
            if meta.get("fps") is not None and not 23 <= meta["fps"] <= 60:
                raise HTTPException(422, "Instagram requires 23 to 60 frames per second")
            audio = meta.get("audio")
            if audio and (
                audio.get("codec") != "aac"
                or audio.get("sample_rate", 0) > 48000
                or audio.get("channels", 0) not in {1, 2}
            ):
                raise HTTPException(
                    422, "Instagram requires AAC audio, up to 48kHz, mono or stereo"
                )
            if meta.get("pixel_format") not in {None, "yuv420p", "yuvj420p"}:
                raise HTTPException(422, "Instagram requires 4:2:0 video")
            if meta.get("video_bitrate", 0) > 25_000_000:
                raise HTTPException(422, "Instagram video bitrate must not exceed 25Mbps")
            duration = meta.get("duration", 0)
            if not 3 <= duration <= (60 if target.format == "story" else 900):
                raise HTTPException(422, "Video duration is not supported for this format")
            if target.format == "story" and (target.caption or data.caption):
                raise HTTPException(422, "Instagram Stories do not support captions")
            continue
        if not target.format.startswith("tiktok_"):
            raise HTTPException(422, "Choose a TikTok publishing format")
        scope = "video.publish" if target.format == "tiktok_direct" else "video.upload"
        if scope not in account.scopes:
            raise HTTPException(422, f"Account is missing {scope} permission")
        if target.format == "tiktok_direct" and not get_settings().tiktok_direct_post_enabled:
            raise HTTPException(422, "TikTok Direct Post approval is required")
        meta = media.metadata_
        if min(meta.get("width", 0), meta.get("height", 0)) < 360:
            raise HTTPException(422, "TikTok requires both dimensions to be at least 360 pixels")
        if meta.get("fps") is not None and not 23 <= meta["fps"] <= 60:
            raise HTTPException(422, "TikTok requires a frame rate between 23 and 60 fps")
    return media


@router.post("/posts", response_model=PostOutput, status_code=201)
async def create_post(data: PostInput, db: Db, workspace: CurrentWorkspace):
    await validate_post(data, db, workspace.id)
    post = Post(
        workspace_id=workspace.id,
        media_id=data.media_id,
        caption=data.caption,
        timezone=data.timezone,
    )
    db.add(post)
    await db.flush()
    for target in data.targets:
        db.add(PostTarget(post_id=post.id, **target.model_dump()))
    await db.flush()
    return await output(post, db)


@router.get("/posts", response_model=list[PostOutput])
async def list_posts(
    db: Db,
    workspace: CurrentWorkspace,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    rows = await db.scalars(
        select(Post)
        .where(Post.workspace_id == workspace.id)
        .order_by(Post.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return [await output(row, db) for row in rows]


@router.get("/posts/{post_id}", response_model=PostOutput)
async def get_post(post_id: uuid.UUID, db: Db, workspace: CurrentWorkspace):
    return await output(await owned_post(post_id, db, workspace.id), db)


@router.patch("/posts/{post_id}", response_model=PostOutput)
async def update_post(post_id: uuid.UUID, data: PostInput, db: Db, workspace: CurrentWorkspace):
    post = await owned_post(post_id, db, workspace.id)
    targets = await post_targets(db, post.id)
    if any(t.status not in EDITABLE for t in targets):
        raise HTTPException(409, "Only drafts or cancelled posts can be edited")
    await validate_post(data, db, workspace.id)
    for target in targets:
        await db.delete(target)
    await db.flush()
    post.media_id, post.caption, post.timezone = data.media_id, data.caption, data.timezone
    for target in data.targets:
        db.add(PostTarget(post_id=post.id, **target.model_dump()))
    await db.flush()
    return await output(post, db)


@router.delete("/posts/{post_id}", status_code=204)
async def delete_post(post_id: uuid.UUID, db: Db, workspace: CurrentWorkspace):
    post = await owned_post(post_id, db, workspace.id)
    if any(t.status not in EDITABLE for t in await post_targets(db, post.id)):
        raise HTTPException(409, "Only drafts or cancelled posts can be deleted")
    await db.delete(post)


async def dispatch(
    post_id: uuid.UUID, db: Db, workspace_id: uuid.UUID, consent: bool, when: datetime
):
    post = await owned_post(post_id, db, workspace_id)
    targets = await post_targets(db, post.id)
    if not consent:
        raise HTTPException(422, "Explicit consent is required for every selected destination")
    if any(t.status not in EDITABLE for t in targets):
        raise HTTPException(409, "Post has already been dispatched")
    await validate_post(
        PostInput(
            media_id=post.media_id,
            caption=post.caption,
            timezone=post.timezone,
            targets=[
                {
                    "account_id": t.account_id,
                    "format": t.format,
                    "caption": t.caption,
                    "settings": t.settings,
                }
                for t in targets
            ],
        ),
        db,
        workspace_id,
    )
    for target in targets:
        target.status = "scheduled"
        target.scheduled_at = when.astimezone(UTC)
        target.consent_at = datetime.now(UTC)
    await db.flush()
    return await output(post, db)


@router.post("/posts/{post_id}/publish", response_model=PostOutput)
async def publish(post_id: uuid.UUID, data: DispatchInput, db: Db, workspace: CurrentWorkspace):
    return await dispatch(post_id, db, workspace.id, data.consent, datetime.now(UTC))


@router.post("/posts/{post_id}/schedule", response_model=PostOutput)
async def schedule(post_id: uuid.UUID, data: ScheduleInput, db: Db, workspace: CurrentWorkspace):
    if data.scheduled_at <= datetime.now(UTC):
        raise HTTPException(422, "Choose a future time")
    return await dispatch(post_id, db, workspace.id, data.consent, data.scheduled_at)


@router.post("/posts/{post_id}/cancel", response_model=PostOutput)
async def cancel(post_id: uuid.UUID, db: Db, workspace: CurrentWorkspace):
    post = await owned_post(post_id, db, workspace.id)
    targets = await post_targets(db, post.id)
    if any(t.status in {"processing", "uncertain"} for t in targets):
        raise HTTPException(409, "Publishing has begun; cancellation is unavailable")
    for target in targets:
        if target.status in {"draft", "scheduled", "queued", "retry"}:
            target.status = "cancelled"
    await db.flush()
    return await output(post, db)


@router.get("/calendar", response_model=list[PostOutput])
async def calendar(db: Db, workspace: CurrentWorkspace, start: datetime, end: datetime):
    if start.tzinfo is None or end.tzinfo is None or end <= start or (end - start).days > 42:
        raise HTTPException(422, "Select a timezone-aware date range of up to 42 days")
    rows = await db.scalars(
        select(Post)
        .join(PostTarget)
        .where(
            Post.workspace_id == workspace.id,
            PostTarget.scheduled_at >= start,
            PostTarget.scheduled_at < end,
        )
        .distinct()
        .limit(500)
    )
    return [await output(row, db) for row in rows]


@router.get("/dashboard")
async def dashboard(db: Db, workspace: CurrentWorkspace):
    account_count = await db.scalar(
        select(func.count())
        .select_from(SocialAccount)
        .where(SocialAccount.workspace_id == workspace.id, SocialAccount.status == "connected")
    )
    counts = (
        await db.execute(
            select(PostTarget.status, func.count())
            .join(Post)
            .where(Post.workspace_id == workspace.id)
            .group_by(PostTarget.status)
        )
    ).all()
    return {"connected_accounts": account_count, "targets": dict(counts)}
