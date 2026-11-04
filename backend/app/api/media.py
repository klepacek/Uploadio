import asyncio
import uuid

from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.auth import CurrentWorkspace, Db
from app.core.config import get_settings
from app.models.entities import MediaAsset, Post, Workspace
from app.services.media import InvalidMedia, inspect_upload
from app.services.storage import media_url, storage

router = APIRouter(prefix="/api/v1/media", tags=["media"])


class UploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255, pattern=r"^[^/\\]+\.(mp4|mov)$")
    content_type: str = Field(pattern=r"^video/(mp4|quicktime)$")
    size_bytes: int = Field(gt=0)


class CompleteRequest(BaseModel):
    media_id: uuid.UUID


async def owned_media(db: Db, workspace_id: uuid.UUID, media_id: uuid.UUID) -> MediaAsset:
    row = await db.scalar(
        select(MediaAsset)
        .where(MediaAsset.id == media_id, MediaAsset.workspace_id == workspace_id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "Media not found")
    return row


@router.post("/upload-url", status_code=201)
async def upload_url(data: UploadRequest, db: Db, workspace: CurrentWorkspace):
    settings = get_settings()
    if data.size_bytes > settings.max_upload_bytes:
        raise HTTPException(422, "Maximum file size is 500 MB")
    await db.scalar(select(Workspace).where(Workspace.id == workspace.id).with_for_update())
    used = await db.scalar(
        select(func.coalesce(func.sum(MediaAsset.size_bytes), 0)).where(
            MediaAsset.workspace_id == workspace.id
        )
    )
    if (used or 0) + data.size_bytes > settings.workspace_quota_bytes:
        raise HTTPException(409, "Workspace storage quota exceeded")
    media_id = uuid.uuid4()
    key = f"staging/{workspace.id}/{media_id}/source"
    url = await asyncio.to_thread(
        storage().generate_presigned_url,
        "put_object",
        Params={
            "Bucket": settings.r2_bucket,
            "Key": key,
            "ContentType": data.content_type,
            "ContentLength": data.size_bytes,
        },
        ExpiresIn=900,
    )
    db.add(
        MediaAsset(
            id=media_id,
            workspace_id=workspace.id,
            object_key=key,
            filename=data.filename,
            content_type=data.content_type,
            size_bytes=data.size_bytes,
        )
    )
    return {"media_id": media_id, "upload_url": url, "expires_in": 900}


@router.post("/complete")
async def complete(data: CompleteRequest, db: Db, workspace: CurrentWorkspace):
    media = await owned_media(db, workspace.id, data.media_id)
    if media.status == "ready":
        return {"id": media.id, "status": media.status}
    try:
        metadata, thumbnail = await asyncio.to_thread(
            inspect_upload, media.object_key, media.size_bytes
        )
    except InvalidMedia as exc:
        raise HTTPException(422, str(exc)) from exc
    except ClientError as exc:
        raise HTTPException(409, "Upload not available; try again after uploading") from exc
    media.object_key = media.object_key.replace("staging/", "media/", 1)
    media.metadata_ = metadata
    media.thumbnail_key = thumbnail
    media.status = "ready"
    return {"id": media.id, "status": media.status, "metadata": metadata}


@router.get("")
async def list_media(db: Db, workspace: CurrentWorkspace):
    rows = await db.scalars(
        select(MediaAsset)
        .where(MediaAsset.workspace_id == workspace.id)
        .order_by(MediaAsset.created_at.desc())
        .limit(100)
    )
    return [
        {
            "id": row.id,
            "filename": row.filename,
            "size_bytes": row.size_bytes,
            "status": row.status,
            "metadata": row.metadata_,
            "url": media_url(row.object_key) if row.status == "ready" else None,
            "thumbnail_url": media_url(row.thumbnail_key) if row.thumbnail_key else None,
        }
        for row in rows
    ]


@router.delete("/{media_id}", status_code=204)
async def delete_media(media_id: uuid.UUID, db: Db, workspace: CurrentWorkspace):
    media = await owned_media(db, workspace.id, media_id)
    if await db.scalar(select(Post.id).where(Post.media_id == media.id).limit(1)):
        raise HTTPException(409, "Delete posts using this media first")
    keys = [media.object_key]
    if media.object_key.startswith("media/"):
        keys.append(media.object_key.replace("media/", "staging/", 1))
    if media.thumbnail_key:
        keys.append(media.thumbnail_key)
    await asyncio.to_thread(
        storage().delete_objects,
        Bucket=get_settings().r2_bucket,
        Delete={"Objects": [{"Key": key} for key in keys]},
    )
    await db.delete(media)
