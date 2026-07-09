"""Review service — CRUD + submission with aggregates and storage."""

import logging
import math
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
from app.services import list_service, spot_cache
from app.services.aggregates import empty_aggregates, update_or_init_aggregates
from app.services.geo import bounding_box, haversine_km
from app.services.storage_service import (
    cleanup,
    delete_review_blobs,
    upload_photos,
    validate_photo_count,
)
from app.services.user_service import DELETED_USER_ID, get_users_by_ids

log = logging.getLogger(__name__)


def _attach_authors(reviews: list[dict]) -> list[dict]:
    """Enrich each review with the author's CURRENT display_name + photo_url via a
    single batched user lookup (read-time join — avoids denormalizing author info
    onto review docs, so a profile rename/avatar change is reflected immediately).

    Mutates and returns the same dicts. Deleted/missing authors get a placeholder.
    """
    uids = [r.get("user_id") for r in reviews]
    authors = get_users_by_ids(uids)
    for r in reviews:
        uid = r.get("user_id")
        if uid == DELETED_USER_ID:
            r["author_name"], r["author_photo_url"] = "Deleted user", None
        else:
            a = authors.get(uid) or {}
            r["author_name"] = a.get("display_name")
            r["author_photo_url"] = a.get("photo_url")
    return reviews


async def get_review(review_id: str) -> dict:
    """Fetch a single review by ID. Raises ReviewNotFound if missing."""
    ref = db.collection("reviews").document(review_id)
    snap = ref.get()
    if not snap.exists:
        raise ReviewNotFound()
    data = snap.to_dict()
    data["id"] = snap.id
    return _attach_authors([data])[0]


# Free-text fields searched by search_reviews_for_spot.
_REVIEW_TEXT_FIELDS = ("notes", "gear_recommendations", "composition_hints")

# --- Scout Sort (quality blend) tuning ---
_SCOUT_RATING_W = 0.5
_SCOUT_RECENCY_W = 0.3
_SCOUT_RICHNESS_W = 0.2
_RECENCY_HALF_LIFE_DAYS = 30.0  # a review's recency weight halves every 30 days


def _review_matches(review: dict, q: str) -> bool:
    """True if the lowercased query is a substring of any of the review's text fields."""
    return any(q in (review.get(f) or "").lower() for f in _REVIEW_TEXT_FIELDS)


def _load_spot_reviews(spot_id: str) -> list[dict]:
    """Load a spot's full review set (newest-first) as dicts with `id` set.

    One index-backed query (reuses the (spot_id ASC, created_at DESC) composite
    index). This is the in-memory scan that backs the feed + search: bounded per
    spot, so fine at current scale. The scale path is a denormalized scout_score
    field + index-backed sorts — mirrors the note in spot_service.search_by_name.
    """
    docs = (
        db.collection("reviews")
        .where("spot_id", "==", spot_id)
        .order_by("created_at", direction="DESCENDING")
        .stream()
    )
    out = []
    for doc in docs:
        d = doc.to_dict()
        d["id"] = doc.id
        out.append(d)
    return out


def _created_ts(review: dict) -> float:
    """POSIX timestamp of created_at (0.0 if missing) for use in sort keys."""
    created = review.get("created_at")
    return created.timestamp() if created else 0.0


def _scout_score(review: dict, now: datetime) -> float:
    """Quality blend in [0, 1]: rating + recency decay + content richness.

    Surfaces high-rated, recent, detailed reviews. See README "Review Sorting".
    """
    rating = (review.get("overall_rating") or 0) / 5.0

    created = review.get("created_at")
    age_days = max((now - created).total_seconds() / 86400.0, 0.0) if created else 0.0
    recency = math.exp(-math.log(2) * age_days / _RECENCY_HALF_LIFE_DAYS)

    richness = (
        (len(review.get("photo_urls") or []) > 1)
        + bool((review.get("notes") or "").strip())
        + bool((review.get("gear_recommendations") or "").strip())
        + bool((review.get("composition_hints") or "").strip())
    ) / 4.0

    return _SCOUT_RATING_W * rating + _SCOUT_RECENCY_W * recency + _SCOUT_RICHNESS_W * richness


def _sort_reviews(reviews: list[dict], sort: str) -> None:
    """Sort reviews in place by the requested mode.

    Keys always end with `id` as a final tiebreak so ordering is deterministic
    across requests — the position-based cursor depends on it.
    """
    if sort == "highest_rated":
        reviews.sort(key=lambda r: (-(r.get("overall_rating") or 0), -_created_ts(r), r["id"]))
    elif sort == "lowest_rated":
        reviews.sort(key=lambda r: ((r.get("overall_rating") or 0), -_created_ts(r), r["id"]))
    elif sort == "scout":
        now = datetime.now(timezone.utc)
        reviews.sort(key=lambda r: (-_scout_score(r, now), -_created_ts(r), r["id"]))
    else:  # "newest"
        reviews.sort(key=lambda r: (-_created_ts(r), r["id"]))


def _paginate_in_memory(items: list[dict], limit: int, cursor: str | None) -> dict:
    """Page an already-sorted list with a position-based (doc-id) cursor.

    The cursor is the id of the last item on the previous page; an unknown cursor
    → InvalidCursor. Returns the PaginatedReviews shape with authors attached.
    """
    start = 0
    if cursor:
        start = next((i + 1 for i, m in enumerate(items) if m["id"] == cursor), None)
        if start is None:
            raise InvalidCursor()

    page = items[start : start + limit]
    next_cursor = page[-1]["id"] if len(items) > start + limit else None
    return {"items": _attach_authors(page), "limit": limit, "next_cursor": next_cursor}


async def get_reviews_for_spot(
    spot_id: str, limit: int = 20, cursor: str | None = None, sort: str = "newest"
) -> dict:
    """
    Paginated reviews for a spot, sorted by `sort` (default newest-first).

    Scans the spot's full review set and sorts + paginates in memory — see
    _load_spot_reviews for the scan/scale notes and _sort_reviews for the modes.
    """
    limit = min(limit, 50)  # hard cap
    reviews = _load_spot_reviews(spot_id)
    _sort_reviews(reviews, sort)
    return _paginate_in_memory(reviews, limit, cursor)


async def search_reviews_for_spot(
    spot_id: str, q: str, limit: int = 20, cursor: str | None = None, sort: str = "newest"
) -> dict:
    """
    Search a single spot's reviews by review text, sorted by `sort`, paginated.

    Matches a case-insensitive substring of the query against the reviewer's
    free-text fields (notes / gear_recommendations / composition_hints), then
    sorts + paginates the matches in memory (same scan as get_reviews_for_spot).
    """
    limit = min(limit, 50)  # hard cap
    q = q.strip().lower()
    if not q:
        return {"items": [], "limit": limit, "next_cursor": None}

    matches = [r for r in _load_spot_reviews(spot_id) if _review_matches(r, q)]
    _sort_reviews(matches, sort)
    return _paginate_in_memory(matches, limit, cursor)


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

    return {"items": _attach_authors(items), "limit": limit, "next_cursor": next_cursor}


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
    spot_data = spot_snap.to_dict()
    spot_name = spot_data["name"]

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
        "public_lat": spot_data["public_lat"],
        "public_lng": spot_data["public_lng"],
        "city": spot_data["city"],
        "admin_area": spot_data["admin_area"],
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

    # Spot aggregates changed — drop the cached snapshot on this instance.
    spot_cache.invalidate()

    return _attach_authors([{**review_dict, "id": review_id, "spot_id": spot_id}])[0]


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
        "public_lat": lat,
        "public_lng": lng,
        "city": geo_data["city"],
        "admin_area": geo_data["admin_area"],
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

    # New spot added — drop the cached snapshot on this instance.
    spot_cache.invalidate()

    spot_dict["id"] = spot_id
    review_dict["id"] = review_id

    return {"spot": spot_dict, "review": _attach_authors([review_dict])[0]}


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

# AI-summary fields live outside the incremental aggregate machinery, so they'd
# be lost when delete_review rebuilds aggregates from scratch. Carry them over so
# a delete doesn't wipe the summary; the post-commit refresh (debounced) decides
# whether it's stale enough to regenerate.
_SPOT_AI_SUMMARY_FIELDS = (
    "ai_summary",
    "ai_summary_review_count",
    "ai_summary_generated_at",
    "ai_summary_model",
)


async def delete_review(review_id: str, uid: str) -> str | None:
    """
    Delete a review (author only) and reverse its effect on the spot.

    Returns the affected spot_id (so the caller can refresh its AI summary), or
    None if the spot was deleted along with its last review.

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
                return True  # spot deleted → saved lists need cleanup

            spot_data = spot_snap.to_dict() or {}
            rebuilt = {
                **{k: spot_data.get(k) for k in _SPOT_IDENTITY_FIELDS},
                **empty_aggregates(),
                # Preserve the AI summary across the rebuild — it isn't an
                # incremental aggregate, so empty_aggregates() doesn't hold it.
                **{k: spot_data[k] for k in _SPOT_AI_SUMMARY_FIELDS if k in spot_data},
            }
            for rid, rdoc in remaining:
                rebuilt = update_or_init_aggregates(rebuilt, rdoc, rid)
            txn.set(spot_ref, rebuilt)
            return False

        spot_deleted = _delete_in_txn(transaction)
    except GoogleAPICallError as e:
        log.error("Delete transaction failed: %s", str(e))
        raise UpstreamUnavailable()
    except Exception as e:
        log.error("Delete transaction failed: %s", str(e))
        raise InternalError()

    # Spot aggregates changed (or the spot was removed) — drop the cached snapshot.
    spot_cache.invalidate()

    # If the spot itself was deleted (last review removed), scrub its id from every
    # saved list so spot_count stays truthful. Best-effort, post-commit (like the
    # photo cleanup below) — a failure here must not fail the committed delete; the
    # lazy prune in get_list_spots is the safety net.
    if spot_deleted:
        try:
            list_service.remove_spot_from_all_lists(spot_id)
        except Exception as e:
            log.error("Saved-list cleanup after spot delete failed: %s", str(e))

    # Photos can't be removed inside a Firestore txn — clean them up post-commit.
    await delete_review_blobs(review_id)

    # Surviving spot → caller refreshes its summary; None if the spot is gone.
    return None if spot_deleted else spot_id


async def edit_review(review_id: str, patch: dict, uid: str) -> tuple[dict, str]:
    """
    Edit one of the caller's own reviews (content fields only) and re-derive the
    spot's aggregates.

    `patch` holds only the fields the client actually sent (exclude_unset); an
    empty patch is a no-op that returns the review unchanged. Photos, spot
    association, and identity fields aren't editable.

    Returns (updated_review_with_authors, spot_id) so the caller can refresh the
    spot's AI summary. Raises ReviewNotFound (404) / Forbidden (403).

    Aggregates aren't incrementally reversible (mode fields, recency-capped
    lists), so — exactly like delete_review — we rebuild the spot from scratch by
    replaying every review in chronological order, with the edited review's new
    values swapped in.
    """
    review_ref = db.collection("reviews").document(review_id)
    snap = review_ref.get()
    if not snap.exists:
        raise ReviewNotFound()
    review = snap.to_dict()
    if review.get("user_id") != uid:
        raise Forbidden("You can only edit your own review")

    spot_id = review["spot_id"]

    # Nothing to change → return the current review as-is (no txn, no summary churn).
    if not patch:
        return _attach_authors([{**review, "id": review_id}])[0], spot_id

    now = datetime.now(timezone.utc)
    patch = {**patch, "updated_at": now}
    spot_ref = db.collection("spots").document(spot_id)
    transaction = db.transaction()

    try:

        @firestore.transactional
        def _edit_in_txn(txn):
            # --- reads first (Firestore requires all reads before writes) ---
            spot_snap = spot_ref.get(transaction=txn)
            reviews = [
                (d.id, d.to_dict())
                for d in db.collection("reviews")
                .where("spot_id", "==", spot_id)
                .get(transaction=txn)
            ]
            # Apply the edit in memory to the target review before replaying.
            reviews = [
                (rid, {**rdoc, **patch} if rid == review_id else rdoc)
                for rid, rdoc in reviews
            ]
            reviews.sort(key=lambda kv: kv[1]["created_at"])

            spot_data = spot_snap.to_dict() or {}
            rebuilt = {
                **{k: spot_data.get(k) for k in _SPOT_IDENTITY_FIELDS},
                **empty_aggregates(),
                # AI summary lives outside the aggregate machinery — carry it over
                # so the rebuild doesn't wipe it (post-commit refresh decides staleness).
                **{k: spot_data[k] for k in _SPOT_AI_SUMMARY_FIELDS if k in spot_data},
            }
            for rid, rdoc in reviews:
                rebuilt = update_or_init_aggregates(rebuilt, rdoc, rid)

            # --- writes ---
            txn.update(review_ref, patch)
            txn.set(spot_ref, rebuilt)

        _edit_in_txn(transaction)
    except (ReviewNotFound, Forbidden):
        raise
    except GoogleAPICallError as e:
        log.error("Edit transaction failed: %s", str(e))
        raise UpstreamUnavailable()
    except Exception as e:
        log.error("Edit transaction failed: %s", str(e))
        raise InternalError()

    # Spot aggregates changed — drop the cached snapshot on this instance.
    spot_cache.invalidate()

    updated = _attach_authors([{**review, **patch, "id": review_id}])[0]
    return updated, spot_id
