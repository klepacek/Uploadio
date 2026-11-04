import asyncio
import os
import shutil
import subprocess
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.entities import Base, MediaAsset, Post, PostTarget, SocialAccount, User, Workspace
from app.services.media import validate_probe
from app.workers.tasks import claim_due, claim_target


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg not installed"
)
def test_real_video_metadata(tmp_path):
    import json

    video = tmp_path / "clip.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=360x640:r=30",
            "-t",
            "1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        check=True,
    )
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(video)],
        check=True,
        capture_output=True,
    )
    metadata = validate_probe(json.loads(result.stdout))
    assert metadata["width"] == 360 and metadata["fps"] == 30


@pytest.mark.skipif(not os.getenv("POSTGRES_TEST_URL"), reason="PostgreSQL test URL not configured")
async def test_postgres_concurrent_claims():
    url = os.environ["POSTGRES_TEST_URL"]
    schema = f"test_{uuid.uuid4().hex}"
    admin = create_async_engine(url)
    async with admin.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as db:
            user = User(email="test@example.com")
            db.add(user)
            await db.flush()
            workspace = Workspace(owner_id=user.id, name="Test")
            db.add(workspace)
            await db.flush()
            media = MediaAsset(
                workspace_id=workspace.id,
                object_key="test",
                filename="test.mp4",
                content_type="video/mp4",
                size_bytes=100,
            )
            account = SocialAccount(
                workspace_id=workspace.id,
                platform="tiktok",
                external_id="1",
                username="test",
                access_token="encrypted",
            )
            db.add_all([media, account])
            await db.flush()
            post = Post(workspace_id=workspace.id, media_id=media.id)
            db.add(post)
            await db.flush()
            target = PostTarget(
                post_id=post.id,
                account_id=account.id,
                format="tiktok_draft",
                status="scheduled",
                scheduled_at=datetime.now(UTC),
            )
            db.add(target)
            await db.commit()
            target_id = target.id

        async def dispatch():
            async with factory() as db:
                return await claim_due(db, datetime.now(UTC))

        results = await asyncio.gather(dispatch(), dispatch())
        assert sum(len(result) for result in results) == 1

        async def claim():
            async with factory() as db:
                return await claim_target(db, target_id)

        results = await asyncio.gather(claim(), claim())
        assert sum(result is not None for result in results) == 1
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()
