"""User service — read-through user doc creation from token claims."""

import logging
from datetime import datetime, timezone

from firebase_admin import auth
from google.api_core.exceptions import GoogleAPICallError

from app.core.exceptions import InternalError, UpstreamUnavailable
from app.core.firebase import db

log = logging.getLogger(__name__)

# Reviews are community data, so on account deletion we keep them but detach the
# author by reassigning user_id to this sentinel rather than cascade-deleting.
DELETED_USER_ID = "deleted_user"

# Firestore caps a batched write at 500 ops; stay under it with headroom.
_BATCH_LIMIT = 450


async def get_or_create_user(uid: str, token_claims: dict) -> dict:
    """
    First call creates the doc from token claims; subsequent calls just read.

    Concurrent first-hits are safe — both writes produce identical identity data,
    last-write-wins via .set(merge=True). No transaction needed.

    A review submitted before the user's first /users/me call can create a
    "count-only" doc (just review_count, via an atomic Increment). Such a doc
    lacks identity fields, so we backfill them here while preserving the count.
    """
    ref = db.collection("users").document(uid)
    snap = ref.get()
    existing = snap.to_dict() if snap.exists else {}

    if "email" in existing:  # already initialized
        existing["review_count"] = max(0, existing.get("review_count", 0))
        # Default notification prefs for docs created before they existed.
        existing.setdefault("email_notifications", True)
        existing.setdefault("push_notifications", True)
        return {**existing, "id": uid}

    # Doc absent, or count-only — backfill identity, preserving any counted reviews.
    identity = {
        "id": uid,
        "email": token_claims.get("email", ""),
        "display_name": token_claims.get("name", ""),
        "photo_url": token_claims.get("picture"),
        "created_at": datetime.now(timezone.utc),
        "email_notifications": True,
        "push_notifications": True,
    }
    ref.set(identity, merge=True)
    return {"review_count": max(0, existing.get("review_count", 0)), **existing, **identity}


async def update_user(uid: str, token_claims: dict, updates: dict) -> dict:
    """
    Update the caller's own profile fields (e.g. home_city/home_country).

    `updates` is the PATCH body with unset fields already excluded, so only the
    keys the client actually sent are written. Ensures the doc exists first
    (read-through create/backfill), then merges the changes.
    """
    user = await get_or_create_user(uid, token_claims)

    if updates:
        db.collection("users").document(uid).set(updates, merge=True)

    return {**user, **updates}


def _anonymize_reviews(uid: str) -> None:
    """Detach the user's reviews by reassigning user_id to the deleted sentinel.

    Reviews (and their photos) stay as community content, so spot aggregates are
    unaffected. Batched in chunks under Firestore's 500-op limit.
    """
    batch = db.batch()
    pending = 0
    for doc in db.collection("reviews").where("user_id", "==", uid).stream():
        batch.update(doc.reference, {"user_id": DELETED_USER_ID})
        pending += 1
        if pending == _BATCH_LIMIT:
            batch.commit()
            batch = db.batch()
            pending = 0
    if pending:
        batch.commit()


async def delete_account(uid: str) -> None:
    """
    Delete the caller's account (right-to-erasure), preserving community data.

    1. Anonymize the user's reviews (reassign user_id → DELETED_USER_ID).
    2. Hard-delete the user doc (the PII: email, display_name, photo_url).
    3. Delete the Firebase Auth user via the Admin SDK.

    Firestore work runs before the Auth delete so the PII removal is the durable
    part; every step is idempotent, so a client retry after a transient Auth
    failure completes cleanly.
    """
    try:
        _anonymize_reviews(uid)
        db.collection("users").document(uid).delete()
    except GoogleAPICallError as e:
        log.error("Account deletion (Firestore) failed: %s", str(e))
        raise UpstreamUnavailable()
    except Exception as e:
        log.error("Account deletion (Firestore) failed: %s", str(e))
        raise InternalError()

    try:
        auth.delete_user(uid)
    except auth.UserNotFoundError:
        pass  # Already gone — idempotent.
    except Exception as e:
        log.error("Account deletion (Auth) failed: %s", str(e))
        raise UpstreamUnavailable()
