"""Review service — CRUD + submission with aggregates and storage."""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from firebase_admin import firestore
from google.api_core.exceptions import GoogleAPICallError

from app.core.exceptions import (
    Forbidden,
    InternalError,
    InvalidCursor,
    ReviewAlreadyExists,
    ReviewNotFound,
    SpotAlreadyExists,
    SpotNotFound,
    UpstreamUnavailable,
)
from app.core.firebase import db
from app.schemas.review import (
    _CREATE_ONLY_FIELDS,
    _SPOT_ONLY_FIELDS,
    ReviewCreate,
    SpotWithReviewCreate,
)
from app.services.aggregates import empty_aggregates, update_or_init_aggregates
from app.services.geo import bounding_box, haversine_km
from app.services.storage_service import (
    cleanup,
    delete_review_blobs,
    upload_photos,
    validate_photo_count,
)

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


async def get_reviews_for_user(user_id: str, limit: int = 10, cursor: str | None = None) -> dict:
    """
    Paginated reviews for a user, newest first.
    Uses composite index (user_id ASC, created_at DESC).
    """
    limit = min(limit, 30)  # hard cap

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


def _existing_review_id(spot_id: str, uid: str, txn=None) -> str | None:
    """Return the id of this user's existing review for the spot, or None.

    Enforces one-review-per-user-per-spot. The two equality filters are served
    by Firestore's automatic single-field indexes (no composite index needed).
    """
    query = (
        db.collection("reviews")
        .where("spot_id", "==", spot_id)
        .where("user_id", "==", uid)
        .limit(1)
    )
    docs = list(query.get(transaction=txn) if txn is not None else query.get())
    return docs[0].id if docs else None


async def submit_review(
    spot_id: str,
    data: ReviewCreate,
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
    validate_photo_count(data.photos)

    # 2. Verify spot exists
    spot_ref = db.collection("spots").document(spot_id)
    spot_snap = spot_ref.get()
    if not spot_snap.exists:
        raise SpotNotFound()
    spot_name = spot_snap.to_dict()["name"]

    # 2b. One review per user per spot — fast fail before wasting a photo upload.
    #     The transaction below re-checks to close the concurrent-submit race.
    existing_id = _existing_review_id(spot_id, uid)
    if existing_id is not None:
        raise ReviewAlreadyExists(spot_id=spot_id, review_id=existing_id)

    # 3. Upload photos
    review_id = str(uuid4())
    photo_urls, photo_paths = await upload_photos(review_id, data.photos)

    # 4. Firestore transaction
    review_ref = db.collection("reviews").document(review_id)
    review_dict = {
        **data.model_dump(exclude=_CREATE_ONLY_FIELDS),
        "spot_id": spot_id,
        "spot_name": spot_name,
        "user_id": uid,
        "photo_urls": photo_urls,
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

            # Re-check one-review-per-user inside the txn to close the race window
            existing_id = _existing_review_id(spot_id, uid, txn=txn)
            if existing_id is not None:
                raise ReviewAlreadyExists(spot_id=spot_id, review_id=existing_id)

            # Update aggregates
            updated_spot = update_or_init_aggregates(spot_data, review_dict, review_id)

            # Write review + spot, and bump the author's denormalized review_count
            txn.set(review_ref, review_dict)
            txn.set(spot_ref, updated_spot)
            txn.set(
                db.collection("users").document(uid),
                {"review_count": firestore.Increment(1)},
                merge=True,
            )

        _submit_in_txn(transaction)
    except (SpotNotFound, ReviewAlreadyExists):
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

    return {**review_dict, "id": review_id, "spot_id": spot_id}


async def submit_with_new_spot(
    data: SpotWithReviewCreate,
    uid: str,
    geo_data: dict,
) -> dict:
    """
    Create a new spot + first review atomically.

    Uses a FIRESTORE TRANSACTION to verify that no duplicate spot exists nearby
    (within 50 meters) before performing writes, preventing race conditions.

    Flow:
    1. Validate photo count
    2. Geocoding already done by caller (geo_data passed in)
    3. Upload photos to Storage
    4. Build spot + review docs, run duplicate check & write inside transaction
    5. On failure → cleanup photos
    """
    now = datetime.now(timezone.utc)
    lat, lng = data.lat, data.lng

    # 1. Validate photo count
    validate_photo_count(data.photos)

    # 2. Generate IDs
    spot_id = str(uuid4())
    review_id = str(uuid4())

    # 3. Upload photos
    photo_urls, photo_paths = await upload_photos(review_id, data.photos)

    # 4. Build docs (drop spot-only and create-only fields from the review payload)
    review_dict = {
        **data.model_dump(exclude=_CREATE_ONLY_FIELDS | _SPOT_ONLY_FIELDS),
        "spot_id": spot_id,
        "spot_name": data.name,
        "user_id": uid,
        "photo_urls": photo_urls,
        "created_at": now,
    }

    spot_dict = {
        "name": data.name,
        "public_lat": lat,
        "public_lng": lng,
        "city": geo_data["city"],
        "admin_area": geo_data["admin_area"],
        "country": geo_data["country"],
        "created_at": now,
        **empty_aggregates(),
    }
    spot_dict = update_or_init_aggregates(spot_dict, review_dict, review_id)

    # 5. Run transaction with duplicate spot verification
    spot_ref = db.collection("spots").document(spot_id)
    review_ref = db.collection("reviews").document(review_id)
    transaction = db.transaction()

    DUPLICATE_SPOT_THRESHOLD_KM = 0.05  # 50 meters

    try:

        @firestore.transactional
        def _submit_in_txn(txn):
            # Check for nearby spots inside the transaction
            min_lat, max_lat, min_lng, max_lng = bounding_box(lat, lng, DUPLICATE_SPOT_THRESHOLD_KM)
            query = (
                db.collection("spots")
                .where("public_lat", ">=", min_lat)
                .where("public_lat", "<=", max_lat)
            )
            candidates = list(query.get(transaction=txn))
            for doc in candidates:
                s = doc.to_dict()
                if not (min_lng <= s["public_lng"] <= max_lng):
                    continue
                d = haversine_km(lat, lng, s["public_lat"], s["public_lng"])
                if d <= DUPLICATE_SPOT_THRESHOLD_KM:
                    raise SpotAlreadyExists(
                        spot_id=doc.id,
                        name=s["name"],
                        distance_m=d * 1000.0,
                    )

            # Perform atomic writes + bump the author's denormalized review_count
            txn.set(spot_ref, spot_dict)
            txn.set(review_ref, review_dict)
            txn.set(
                db.collection("users").document(uid),
                {"review_count": firestore.Increment(1)},
                merge=True,
            )

        _submit_in_txn(transaction)
    except SpotAlreadyExists:
        await cleanup(photo_paths)
        raise
    except GoogleAPICallError as e:
        log.error("Transaction failed: %s", str(e))
        await cleanup(photo_paths)
        raise UpstreamUnavailable()
    except Exception as e:
        log.error("Transaction failed: %s", str(e))
        await cleanup(photo_paths)
        raise InternalError()

    spot_dict["id"] = spot_id
    review_dict["id"] = review_id

    return {"spot": spot_dict, "review": review_dict}


# Spot identity fields carried across an aggregate rebuild (everything that
# isn't a derived aggregate).
_SPOT_IDENTITY_FIELDS = (
    "name",
    "public_lat",
    "public_lng",
    "city",
    "admin_area",
    "country",
    "created_at",
)


async def delete_review(review_id: str, uid: str) -> None:
    """
    Delete a review (author only) and reverse its effect on the spot.

    Flow:
    1. Load the review → 404 if missing, 403 if not the author.
    2. TRANSACTION: delete the review, decrement the author's review_count, and
       rebuild the spot's aggregates from the *remaining* reviews. Mode fields
       and the recency-capped lists (recent_review_photos, gear/comp tips) aren't
       reversible incrementally, so we recompute from scratch by replaying the
       survivors in chronological order — the exact order they were added.
       If it was the spot's only review, the now-empty spot is deleted too.
    3. After commit → best-effort delete of the review's photos from Storage.
    """
    review_ref = db.collection("reviews").document(review_id)
    snap = review_ref.get()
    if not snap.exists:
        raise ReviewNotFound()
    review = snap.to_dict()
    if review.get("user_id") != uid:
        raise Forbidden("You can only delete your own review")

    spot_id = review["spot_id"]
    spot_ref = db.collection("spots").document(spot_id)
    transaction = db.transaction()

    try:

        @firestore.transactional
        def _delete_in_txn(txn):
            # --- reads first (Firestore requires all reads before writes) ---
            spot_snap = spot_ref.get(transaction=txn)
            remaining = [
                (d.id, d.to_dict())
                for d in db.collection("reviews")
                .where("spot_id", "==", spot_id)
                .get(transaction=txn)
                if d.id != review_id
            ]
            remaining.sort(key=lambda kv: kv[1]["created_at"])

            # --- writes ---
            txn.delete(review_ref)
            txn.set(
                db.collection("users").document(uid),
                {"review_count": firestore.Increment(-1)},
                merge=True,
            )

            if not remaining:
                # Last review removed → the spot has no content; remove it.
                if spot_snap.exists:
                    txn.delete(spot_ref)
                return

            spot_data = spot_snap.to_dict() or {}
            rebuilt = {
                **{k: spot_data.get(k) for k in _SPOT_IDENTITY_FIELDS},
                **empty_aggregates(),
            }
            for rid, rdoc in remaining:
                rebuilt = update_or_init_aggregates(rebuilt, rdoc, rid)
            txn.set(spot_ref, rebuilt)

        _delete_in_txn(transaction)
    except GoogleAPICallError as e:
        log.error("Delete transaction failed: %s", str(e))
        raise UpstreamUnavailable()
    except Exception as e:
        log.error("Delete transaction failed: %s", str(e))
        raise InternalError()

    # Photos can't be removed inside a Firestore txn — clean them up post-commit.
    await delete_review_blobs(review_id)
