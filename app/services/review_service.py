"""Review service — CRUD + submission with aggregates and storage."""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import UploadFile
from firebase_admin import firestore
from google.api_core.exceptions import GoogleAPICallError

from app.core.exceptions import (
    InternalError,
    InvalidCursor,
    ReviewNotFound,
    SpotNotFound,
    UpstreamUnavailable,
)
from app.core.firebase import db
from app.services.aggregates import empty_aggregates, update_or_init_aggregates
from app.services.storage_service import cleanup, upload_photos, validate_photo_count

log = logging.getLogger(__name__)


async def get_review(review_id: str) -> dict:
    """Fetch a single review by ID. Raises ReviewNotFound if missing."""
    ref = db.collection("reviews").document(review_id)
    snap = ref.get()
    if not snap.exists:
        raise ReviewNotFound()
    data = snap.to_dict()
    data["id"] = snap.id
    return data


async def get_reviews_for_spot(spot_id: str, limit: int = 20, cursor: str | None = None) -> dict:
    """
    Paginated reviews for a spot, newest first.
    Uses composite index (spot_id ASC, created_at DESC).
    """
    limit = min(limit, 50)  # hard cap

    query = (
        db.collection("reviews")
        .where("spot_id", "==", spot_id)
        .order_by("created_at", direction="DESCENDING")
    )

    if cursor:
        try:
            cursor_doc = db.collection("reviews").document(cursor).get()
            if not cursor_doc.exists:
                raise InvalidCursor()
            query = query.start_after(cursor_doc)
        except InvalidCursor:
            raise
        except Exception:
            raise InvalidCursor()

    # Fetch limit + 1 to determine if there's a next page
    docs = list(query.limit(limit + 1).stream())

    items = []
    for doc in docs[:limit]:
        d = doc.to_dict()
        d["id"] = doc.id
        items.append(d)

    next_cursor = docs[limit - 1].id if len(docs) > limit else None

    return {"items": items, "limit": limit, "next_cursor": next_cursor}


async def get_reviews_for_user(user_id: str, limit: int = 20, cursor: str | None = None) -> dict:
    """
    Paginated reviews for a user, newest first.
    Uses composite index (user_id ASC, created_at DESC).
    """
    limit = min(limit, 50)  # hard cap

    query = (
        db.collection("reviews")
        .where("user_id", "==", user_id)
        .order_by("created_at", direction="DESCENDING")
    )

    if cursor:
        try:
            cursor_doc = db.collection("reviews").document(cursor).get()
            if not cursor_doc.exists:
                raise InvalidCursor()
            query = query.start_after(cursor_doc)
        except InvalidCursor:
            raise
        except Exception:
            raise InvalidCursor()

    docs = list(query.limit(limit + 1).stream())

    items = []
    for doc in docs[:limit]:
        d = doc.to_dict()
        d["id"] = doc.id
        items.append(d)

    next_cursor = docs[limit - 1].id if len(docs) > limit else None

    return {"items": items, "limit": limit, "next_cursor": next_cursor}


async def submit_review(
    spot_id: str,
    photos: list[UploadFile],
    overall_rating: int,
    notes: str,
    best_time_of_day: list[str],
    access_level: str,
    entrance_fee: str,
    crowd_level: str,
    environment: str,
    uid: str,
) -> dict:
    """
    Submit a review for an existing spot.

    Flow:
    1. Validate photo count
    2. Verify spot exists → 404 SPOT_NOT_FOUND
    3. Upload photos to Storage (validates format + size during upload)
    4. Firestore TRANSACTION: read spot → write review + update aggregates
    5. On transaction failure → cleanup uploaded photos, raise InternalError
    """
    now = datetime.now(timezone.utc)

    # 1. Validate photo count
    validate_photo_count(photos)

    # 2. Verify spot exists
    spot_ref = db.collection("spots").document(spot_id)
    spot_snap = spot_ref.get()
    if not spot_snap.exists:
        raise SpotNotFound()

    # 3. Upload photos
    review_id = str(uuid4())
    photo_urls, photo_paths = await upload_photos(review_id, photos)

    # 4. Firestore transaction
    review_ref = db.collection("reviews").document(review_id)
    review_dict = {
        "spot_id": spot_id,
        "user_id": uid,
        "photo_urls": photo_urls,
        "overall_rating": overall_rating,
        "notes": notes,
        "best_time_of_day": best_time_of_day,
        "access_level": access_level,
        "entrance_fee": entrance_fee,
        "crowd_level": crowd_level,
        "environment": environment,
        "created_at": now,
    }

    transaction = db.transaction()

    try:

        @firestore.transactional
        def _submit_in_txn(txn):
            # Read spot (inside transaction for consistency)
            spot_data = spot_ref.get(transaction=txn).to_dict()
            if spot_data is None:
                raise SpotNotFound()

            # Update aggregates
            updated_spot = update_or_init_aggregates(spot_data, review_dict, review_id)

            # Write both
            txn.set(review_ref, review_dict)
            txn.set(spot_ref, updated_spot)

        _submit_in_txn(transaction)
    except SpotNotFound:
        await cleanup(photo_paths)
        raise
    except GoogleAPICallError as e:
        log.error("Firestore transaction failed: %s", str(e))
        await cleanup(photo_paths)
        raise UpstreamUnavailable()
    except Exception as e:
        log.error("Transaction failed: %s", str(e))
        await cleanup(photo_paths)
        raise InternalError()

    return {**review_dict, "id": review_id}


async def submit_with_new_spot(
    photos: list[UploadFile],
    name: str,
    lat: float,
    lng: float,
    overall_rating: int,
    notes: str,
    best_time_of_day: list[str],
    access_level: str,
    entrance_fee: str,
    crowd_level: str,
    environment: str,
    uid: str,
    geo_data: dict,
) -> dict:
    """
    Create a new spot + first review atomically.

    Uses BATCHED WRITE (not transaction) since both docs are new — no reads needed.

    Flow:
    1. Validate photo count
    2. Geocoding already done by caller (geo_data passed in)
    3. Upload photos to Storage
    4. Build spot + review docs, batch write
    5. On failure → cleanup photos
    """
    now = datetime.now(timezone.utc)

    # 1. Validate photo count
    validate_photo_count(photos)

    # 2. Generate IDs
    spot_id = str(uuid4())
    review_id = str(uuid4())

    # 3. Upload photos
    photo_urls, photo_paths = await upload_photos(review_id, photos)

    # 4. Build docs
    review_dict = {
        "spot_id": spot_id,
        "user_id": uid,
        "photo_urls": photo_urls,
        "overall_rating": overall_rating,
        "notes": notes,
        "best_time_of_day": best_time_of_day,
        "access_level": access_level,
        "entrance_fee": entrance_fee,
        "crowd_level": crowd_level,
        "environment": environment,
        "created_at": now,
    }

    spot_dict = {
        "name": name,
        "public_lat": lat,
        "public_lng": lng,
        "city": geo_data["city"],
        "admin_area": geo_data["admin_area"],
        "country": geo_data["country"],
        "created_at": now,
        **empty_aggregates(),
    }
    spot_dict = update_or_init_aggregates(spot_dict, review_dict, review_id)

    # 5. Batched write — atomic, no reads needed
    spot_ref = db.collection("spots").document(spot_id)
    review_ref = db.collection("reviews").document(review_id)

    try:
        batch = db.batch()
        batch.set(spot_ref, spot_dict)
        batch.set(review_ref, review_dict)
        batch.commit()
    except GoogleAPICallError as e:
        log.error("Batch write failed: %s", str(e))
        await cleanup(photo_paths)
        raise UpstreamUnavailable()
    except Exception as e:
        log.error("Batch write failed: %s", str(e))
        await cleanup(photo_paths)
        raise InternalError()

    spot_dict["id"] = spot_id
    review_dict["id"] = review_id

    return {"spot": spot_dict, "review": review_dict}
