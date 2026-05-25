"""User service — read-through user doc creation from token claims."""

from datetime import datetime, timezone

from app.core.firebase import db


async def get_or_create_user(uid: str, token_claims: dict) -> dict:
    """
    First call creates the doc from token claims; subsequent calls just read.

    Concurrent first-hits are safe — both writes produce identical data,
    last-write-wins via .set(). No transaction needed.
    """
    ref = db.collection("users").document(uid)
    snap = ref.get()

    if snap.exists:
        return {**snap.to_dict(), "uid": uid}

    user_data = {
        "uid": uid,
        "email": token_claims.get("email", ""),
        "display_name": token_claims.get("name", ""),
        "photo_url": token_claims.get("picture"),
        "created_at": datetime.now(timezone.utc),
    }
    ref.set(user_data)
    return user_data
