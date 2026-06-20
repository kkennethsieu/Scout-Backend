"""Saved-list service — list CRUD + spot membership.

Lists are a per-user subcollection: users/{uid}/lists/{listId}. Because they live
under the caller's uid, ownership is enforced by the path — a user can only ever
reach their own lists, so there's no owner check / 403 branch here.

The "Favorites" list has the fixed id "favorites" and always exists (read-through
created). It can't be renamed or deleted (FavoritesProtected).

Membership lives in each list's spot_ids array (insertion order, newest appended
last). spot_count is derived as len(spot_ids) — never a blind Increment — so every
mutation runs read-modify-write inside a transaction and the count can't drift.
"""

import base64
import binascii
import logging
from datetime import datetime, timezone

from firebase_admin import firestore
from google.api_core.exceptions import GoogleAPICallError

from app.core.exceptions import (
    FavoritesProtected,
    InternalError,
    InvalidCursor,
    ListLimitReached,
    ListNotFound,
    UpstreamUnavailable,
)
from app.core.firebase import db
from app.services import spot_service

log = logging.getLogger(__name__)

FAVORITES_ID = "favorites"
FAVORITES_NAME = "Favorites"
LIST_LIMIT = 100  # max lists per user — bounds the set-membership transaction
_BATCH_LIMIT = 450  # Firestore caps a batched write at 500 ops; stay under it.


def _lists_col(uid: str):
    return db.collection("users").document(uid).collection("lists")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_response(doc_id: str, data: dict, cover_photo_url: str | None) -> dict:
    """Shape a stored list doc into the overview response (no raw spot_ids)."""
    return {
        "id": doc_id,
        "name": data.get("name", ""),
        "description": data.get("description"),
        "is_system": doc_id == FAVORITES_ID,
        "spot_count": len(data.get("spot_ids") or []),
        "cover_photo_url": cover_photo_url,
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
    }


def _encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def _decode_cursor(cursor: str) -> int:
    try:
        offset = int(base64.urlsafe_b64decode(cursor.encode()).decode())
        if offset < 0:
            raise ValueError
        return offset
    except (ValueError, binascii.Error, UnicodeDecodeError):
        raise InvalidCursor()


def _favorites_seed() -> dict:
    now = _now()
    return {
        "name": FAVORITES_NAME,
        "description": None,
        "spot_ids": [],
        "created_at": now,
        "updated_at": now,
    }


def _ensure_favorites_doc(uid: str) -> None:
    """Materialize the Favorites doc if it doesn't physically exist yet.

    Favorites is conceptually always-present, so membership mutations targeting it
    must work even before the client has called GET /lists or PUT /favorites.
    """
    ref = _lists_col(uid).document(FAVORITES_ID)
    if not ref.get().exists:
        ref.set(_favorites_seed())


async def list_overview(uid: str) -> dict:
    """All of the user's lists plus the membership map, in one atomic snapshot.

    Returns {"lists": [...], "memberships": {list_id: spot_ids}} — the lists array
    is Favorites-first then created_at ascending, and memberships maps every list
    (even empty ones) to its spot_ids so the client can hydrate heart/checkbox
    state without a second call.

    Read-through-creates Favorites if missing, so the client never has to. The
    cover thumbnail for each list is derived from its newest spot's cover photo,
    resolved in a single batched lookup across every list.
    """
    col = _lists_col(uid)
    docs = {d.id: d.to_dict() for d in col.stream()}

    if FAVORITES_ID not in docs:
        seed = _favorites_seed()
        col.document(FAVORITES_ID).set(seed)
        docs[FAVORITES_ID] = seed

    # Newest spot of each list → resolve cover photos in one batch.
    newest_ids = []
    for data in docs.values():
        spot_ids = data.get("spot_ids") or []
        if spot_ids:
            newest_ids.append(spot_ids[-1])
    spots_by_id = spot_service.get_spots_by_ids(list(dict.fromkeys(newest_ids)))

    def cover_for(data: dict) -> str | None:
        spot_ids = data.get("spot_ids") or []
        if not spot_ids:
            return None
        spot = spots_by_id.get(spot_ids[-1])
        if not spot:
            return None
        photos = spot.get("recent_review_photos") or []
        return photos[0].get("photo_url") if photos else None

    # Favorites first, then created_at ascending (None-safe).
    def sort_key(item):
        doc_id, data = item
        is_fav = 0 if doc_id == FAVORITES_ID else 1
        return (is_fav, data.get("created_at") or datetime.min.replace(tzinfo=timezone.utc))

    ordered = sorted(docs.items(), key=sort_key)
    memberships = {doc_id: list(data.get("spot_ids") or []) for doc_id, data in docs.items()}
    return {
        "lists": [_to_response(doc_id, data, cover_for(data)) for doc_id, data in ordered],
        "memberships": memberships,
    }


async def create_list(uid: str, name: str, description: str | None = None) -> dict:
    """Create a new (auto-id) list. Enforces the per-user list cap."""
    col = _lists_col(uid)
    if len(list(col.list_documents())) >= LIST_LIMIT:
        raise ListLimitReached(LIST_LIMIT)
    now = _now()
    data = {
        "name": name,
        "description": (description or None),
        "spot_ids": [],
        "created_at": now,
        "updated_at": now,
    }
    ref = col.document()
    ref.set(data)
    return _to_response(ref.id, data, None)


async def update_list(uid: str, list_id: str, updates: dict) -> dict:
    """Edit a list's name and/or description. Favorites is protected; missing →
    404. `updates` holds only the fields the client actually sent (exclude_unset):
    a None/blank description clears it; a None name is ignored (non-nullable). An
    empty update is a no-op that returns the list unchanged.
    """
    if list_id == FAVORITES_ID:
        raise FavoritesProtected()
    ref = _lists_col(uid).document(list_id)
    snap = ref.get()
    if not snap.exists:
        raise ListNotFound()

    to_write: dict = {}
    if updates.get("name") is not None:
        to_write["name"] = updates["name"]
    if "description" in updates:
        to_write["description"] = updates["description"] or None

    if to_write:
        to_write["updated_at"] = _now()
        ref.set(to_write, merge=True)
        snap = ref.get()
    return _to_response(list_id, snap.to_dict(), None)


async def delete_list(uid: str, list_id: str) -> None:
    """Delete a list. Favorites is protected; delete is idempotent otherwise."""
    if list_id == FAVORITES_ID:
        raise FavoritesProtected()
    _lists_col(uid).document(list_id).delete()


async def get_list_spots(uid: str, list_id: str, limit: int, cursor: str | None = None) -> dict:
    """Resolve a page of a list's spots, newest first.

    spot_ids is stored oldest→newest; we reverse it, slice by an opaque offset
    cursor, and resolve the slice against the spots collection. Spots that no
    longer exist are skipped (so a page may return fewer than `limit`), and the
    resolved spots are re-sorted back into the sliced order.
    """
    snap = _lists_col(uid).document(list_id).get()
    if not snap.exists:
        raise ListNotFound()

    ordered_ids = list(reversed(snap.to_dict().get("spot_ids") or []))
    start = _decode_cursor(cursor) if cursor else 0
    page_ids = ordered_ids[start : start + limit]

    spots_by_id = spot_service.get_spots_by_ids(page_ids)
    items = [spots_by_id[sid] for sid in page_ids if sid in spots_by_id]

    # Self-heal: prune any dead refs on this page (spots deleted before the
    # proactive cleanup landed, or any that slipped through it). ArrayRemove is
    # atomic, so spot_count — derived as len(spot_ids) — converges to the truth.
    missing = [sid for sid in page_ids if sid not in spots_by_id]
    if missing:
        _lists_col(uid).document(list_id).update(
            {"spot_ids": firestore.ArrayRemove(missing), "updated_at": _now()}
        )

    next_start = start + limit
    next_cursor = _encode_cursor(next_start) if next_start < len(ordered_ids) else None

    return {"items": items, "limit": limit, "next_cursor": next_cursor}


async def set_membership(uid: str, spot_id: str, list_ids: list[str]) -> dict:
    """Set the exact set of lists a spot belongs to, in one transaction.

    Reads every list, diffs current membership against the requested set, and
    writes only the lists that change. Every requested id must be one of the
    user's lists (else 404). Returns the refreshed overview.
    """
    # Validate the spot exists (raises SpotNotFound).
    await spot_service.get_spot(spot_id)

    # Favorites is always a valid target, even if not yet materialized.
    _ensure_favorites_doc(uid)

    requested = set(list_ids)
    col = _lists_col(uid)
    transaction = db.transaction()

    @firestore.transactional
    def _txn(txn):
        docs = list(col.stream(transaction=txn))
        existing_ids = {d.id for d in docs}
        unknown = requested - existing_ids
        if unknown:
            raise ListNotFound()

        now = _now()
        for d in docs:
            data = d.to_dict()
            spot_ids = list(data.get("spot_ids") or [])
            has = spot_id in spot_ids
            want = d.id in requested
            if want and not has:
                spot_ids.append(spot_id)
            elif has and not want:
                spot_ids.remove(spot_id)
            else:
                continue  # no change for this list
            txn.update(d.reference, {"spot_ids": spot_ids, "updated_at": now})

    _run_txn(_txn, transaction)
    return await list_overview(uid)


def remove_spot_from_all_lists(spot_id: str) -> None:
    """Scrub a deleted spot's id from every user's list (collection-group sweep).

    Called after a spot is deleted (its last review removed) so no list keeps a
    dangling reference — spot_count stays truthful (it's derived as len(spot_ids)).
    ArrayRemove is atomic, so this is safe against concurrent membership edits.
    Batched under Firestore's 500-op limit.
    """
    now = _now()
    batch = db.batch()
    pending = 0
    query = db.collection_group("lists").where("spot_ids", "array_contains", spot_id)
    for doc in query.stream():
        batch.update(
            doc.reference, {"spot_ids": firestore.ArrayRemove([spot_id]), "updated_at": now}
        )
        pending += 1
        if pending == _BATCH_LIMIT:
            batch.commit()
            batch = db.batch()
            pending = 0
    if pending:
        batch.commit()


def _run_txn(fn, transaction) -> None:
    """Run a transactional fn with the project's standard error mapping."""
    try:
        fn(transaction)
    except (ListNotFound, FavoritesProtected):
        raise
    except GoogleAPICallError as e:
        log.error("List transaction failed: %s", str(e))
        raise UpstreamUnavailable()
    except Exception as e:
        log.error("List transaction failed: %s", str(e))
        raise InternalError()
