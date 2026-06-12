"""Cloud Storage service — photo upload, validation, and cleanup.

Google Storage SDK is synchronous. We wrap with asyncio.to_thread so it
doesn't block the event loop. For MVP single-instance concurrency this
barely matters, but it's correct and free.
"""

import asyncio
import logging
from io import BytesIO
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image

from app.core.config import settings
from app.core.exceptions import PhotoCountInvalid, PhotoInvalidFormat, PhotoTooLarge
from app.core.firebase import bucket

log = logging.getLogger(__name__)


def _validate_image_content(data: bytes):
    """
    Two-pass Pillow check — verify() consumes the stream, so we reopen.
    JPEG only. PNG/HEIC/anything else rejected.
    """
    try:
        Image.open(BytesIO(data)).verify()
    except Exception:
        raise PhotoInvalidFormat()

    # Re-open after verify() consumed the stream
    img = Image.open(BytesIO(data))
    if img.format != "JPEG":
        raise PhotoInvalidFormat()


def _public_url(path: str) -> str:
    """Build the public URL for a storage object."""
    return f"https://storage.googleapis.com/{settings.STORAGE_BUCKET}/{path}"


def _upload_one_sync(path: str, data: bytes):
    """Synchronous upload — called via asyncio.to_thread."""
    blob = bucket.blob(path)
    blob.upload_from_string(data, content_type="image/jpeg")
    # No make_public() needed — bucket is whole-public via IAM.


def validate_photo_count(files: list[UploadFile]):
    """Validate photo count is 1–5."""
    if not files or len(files) < 1 or len(files) > 5:
        raise PhotoCountInvalid()


async def upload_photos(review_id: str, files: list[UploadFile]) -> tuple[list[str], list[str]]:
    completed: list[tuple[str, str]] = []

    async def upload_one(file: UploadFile) -> tuple[str, str]:
        data = await file.read()
        if len(data) > settings.MAX_PHOTO_BYTES:
            raise PhotoTooLarge()
        _validate_image_content(data)
        data = _strip_exif(data)

        path = f"reviews/{review_id}/photos/{uuid4()}.jpg"
        await asyncio.to_thread(_upload_one_sync, path, data)
        result = (_public_url(path), path)
        completed.append(result)  # track as soon as it's uploaded
        return result

    try:
        results = await asyncio.gather(*[upload_one(f) for f in files])
        return [r[0] for r in results], [r[1] for r in results]
    except Exception:
        await cleanup([r[1] for r in completed])
        raise


def _strip_exif(data: bytes) -> bytes:
    """Re-encode JPEG without EXIF metadata."""
    img = Image.open(BytesIO(data))
    out = BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue()


async def upload_avatar(uid: str, file: UploadFile) -> tuple[str, str]:
    """Validate and upload a single profile photo, returning (public_url, path).

    Same pipeline as review photos — JPEG only, ≤MAX_PHOTO_BYTES, EXIF stripped.
    Stored under users/{uid}/avatar/ so stale avatars can be pruned by prefix.
    """
    data = await file.read()
    if len(data) > settings.MAX_PHOTO_BYTES:
        raise PhotoTooLarge()
    _validate_image_content(data)
    data = _strip_exif(data)

    path = f"users/{uid}/avatar/{uuid4()}.jpg"
    await asyncio.to_thread(_upload_one_sync, path, data)
    return _public_url(path), path


async def delete_avatar_blobs(uid: str, keep_path: str | None = None):
    """Best-effort delete of a user's avatar blobs, optionally keeping one.

    Called after a new avatar is uploaded to prune the previous one(s). Deletes
    by prefix (users/{uid}/avatar/) so it doesn't depend on parsing stored URLs.
    """

    def _delete_prefix_sync(prefix: str):
        for blob in bucket.list_blobs(prefix=prefix):
            if keep_path is not None and blob.name == keep_path:
                continue
            blob.delete()

    try:
        await asyncio.to_thread(_delete_prefix_sync, f"users/{uid}/avatar/")
    except Exception as e:
        log.warning("avatar blob cleanup failed", extra={"uid": uid, "error": str(e)})


async def delete_review_blobs(review_id: str):
    """Best-effort delete of every photo stored under a review's prefix.

    Used when a review is deleted. Deletes by prefix (reviews/{id}/) so it
    doesn't depend on parsing stored URLs back into object paths.
    """

    def _delete_prefix_sync(prefix: str):
        for blob in bucket.list_blobs(prefix=prefix):
            blob.delete()

    try:
        await asyncio.to_thread(_delete_prefix_sync, f"reviews/{review_id}/")
    except Exception as e:
        log.warning("review blob cleanup failed", extra={"review_id": review_id, "error": str(e)})


async def cleanup(paths: list[str]):
    """
    Best-effort delete of storage objects.

    Logs failures as WARNING (not ERROR — these are usually transient,
    self-correcting, and not a critical inconsistency since the Firestore
    write also failed).
    """

    def _delete_sync(p: str):
        bucket.blob(p).delete()

    for path in paths:
        try:
            await asyncio.to_thread(_delete_sync, path)
        except Exception as e:
            log.warning("storage cleanup failed", extra={"path": path, "error": str(e)})
