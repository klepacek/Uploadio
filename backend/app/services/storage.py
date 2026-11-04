from functools import lru_cache

import boto3
from botocore.config import Config
from fastapi import HTTPException

from app.core.config import get_settings


@lru_cache
def storage():
    settings = get_settings()
    if not settings.r2_endpoint_url or not settings.r2_access_key_id:
        raise HTTPException(503, "Media storage is not configured")
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 2}),
    )


def media_url(key: str, expires: int = 3600) -> str:
    return storage().generate_presigned_url(
        "get_object",
        Params={"Bucket": get_settings().r2_bucket, "Key": key},
        ExpiresIn=expires,
    )
