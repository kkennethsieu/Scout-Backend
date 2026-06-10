"""User service — read-through user doc creation from token claims."""

from datetime import datetime, timezone

from app.core.firebase import db


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
        return {**existing, "id": uid}

    # Doc absent, or count-only — backfill identity, preserving any counted reviews.
    identity = {
        "id": uid,
        "email": token_claims.get("email", ""),
        "display_name": token_claims.get("name", ""),
        "photo_url": token_claims.get("picture"),
        "created_at": datetime.now(timezone.utc),
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
