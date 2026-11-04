import json
import subprocess
import tempfile
from pathlib import Path

from app.core.config import get_settings
from app.services.storage import storage


class InvalidMedia(ValueError):
    pass


def validate_probe(data: dict) -> dict:
    streams = data.get("streams", [])
    videos = [stream for stream in streams if stream.get("codec_type") == "video"]
    if len(videos) != 1:
        raise InvalidMedia("Upload a file containing one video stream")
    video = videos[0]
    duration = float(data.get("format", {}).get("duration", 0))
    width, height = int(video.get("width", 0)), int(video.get("height", 0))
    if not 0 < duration <= 600 or not 32 <= width <= 4096 or not 32 <= height <= 4096:
        raise InvalidMedia("Video must be at most 10 minutes and between 32 and 4096 pixels")
    if video.get("codec_name") not in ("h264", "hevc"):
        raise InvalidMedia("Use H.264 or H.265 video in an MP4 or MOV file")
    formats = data.get("format", {}).get("format_name", "").split(",")
    if not set(formats) & {"mov", "mp4"}:
        raise InvalidMedia("Upload an MP4 or MOV file")
    return {"duration": duration, "width": width, "height": height, "codec": video["codec_name"]}


def inspect_upload(key: str, expected_size: int) -> tuple[dict, str]:
    client = storage()
    bucket = get_settings().r2_bucket
    head = client.head_object(Bucket=bucket, Key=key)
    if head["ContentLength"] != expected_size:
        raise InvalidMedia("Uploaded file size differs from the reserved size")
    with tempfile.TemporaryDirectory(prefix="uploadio-") as directory:
        source = Path(directory) / "video.mp4"
        response = client.get_object(Bucket=bucket, Key=key, IfMatch=head["ETag"])
        total = 0
        try:
            with source.open("wb") as output:
                for chunk in response["Body"].iter_chunks(chunk_size=1024 * 1024):
                    total += len(chunk)
                    if total > expected_size:
                        raise InvalidMedia("Uploaded file is too large")
                    output.write(chunk)
        finally:
            response["Body"].close()
        if total != expected_size:
            raise InvalidMedia("Upload is incomplete")
        try:
            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-protocol_whitelist",
                    "file",
                    "-show_format",
                    "-show_streams",
                    "-of",
                    "json",
                    str(source),
                ],
                capture_output=True,
                check=True,
                timeout=30,
            )
            metadata = validate_probe(json.loads(probe.stdout))
            thumbnail = Path(directory) / "thumbnail.jpg"
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-protocol_whitelist",
                    "file",
                    "-i",
                    str(source),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=480:-2",
                    "-y",
                    str(thumbnail),
                ],
                capture_output=True,
                check=True,
                timeout=60,
            )
        except (subprocess.SubprocessError, json.JSONDecodeError) as exc:
            raise InvalidMedia("Unable to read video; check its format") from exc
        thumbnail_key = f"{key}.jpg"
        client.upload_file(
            str(thumbnail), bucket, thumbnail_key, ExtraArgs={"ContentType": "image/jpeg"}
        )
    client.copy_object(
        Bucket=bucket,
        Key=f"{key}.validated",
        CopySource={"Bucket": bucket, "Key": key},
        CopySourceIfMatch=head["ETag"],
    )
    return metadata, thumbnail_key
