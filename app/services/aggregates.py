"""Spot aggregate computation — incremental, purely additive.

NOTE: Purely additive. V2 review deletion will need a sibling function that
decrements counts and recomputes recent_review_photos by querying the
next-most-recent submitted review.
"""


def empty_aggregates() -> dict:
    """
    Factory — fresh dict every call. Don't share mutable defaults.

    Returns baseline aggregate fields for a brand-new spot with no reviews.
    """
    return {
        "review_count": 0,
        "avg_rating": 0.0,
        "access_level_counts": {},
        "entrance_fee_counts": {},
        "crowd_level_counts": {},
        "environment_counts": {},
        "mode_access_level": "",
        "mode_entrance_fee": "",
        "mode_crowd_level": "",
        "mode_environment": "",
        "recent_review_photos": [],
    }


def update_or_init_aggregates(spot_data: dict, new_review: dict, new_review_id: str) -> dict:
    """
    Returns updated aggregate fields. Works for first review (empty spot)
    and subsequent reviews uniformly.

    - Incremental avg_rating (works at old_count=0 since old_avg*0=0)
    - Mode fields via running counts with deterministic tie-break:
      highest count, then alphabetical
    - recent_review_photos: prepend new entry, cap at 5
    """
    s = dict(spot_data)

    # --- avg_rating ---
    old_count = s.get("review_count", 0)
    old_avg = s.get("avg_rating", 0.0)
    new_count = old_count + 1
    s["review_count"] = new_count
    s["avg_rating"] = (old_avg * old_count + new_review["overall_rating"]) / new_count

    # --- mode fields via running counts ---
    for field in ("access_level", "entrance_fee", "crowd_level", "environment"):
        counts_key = f"{field}_counts"
        counts = dict(s.get(counts_key) or {})
        v = new_review[field]
        counts[v] = counts.get(v, 0) + 1
        s[counts_key] = counts
        # Deterministic tie-break: highest count, then alphabetical
        s[f"mode_{field}"] = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

    # --- recent_review_photos: prepend new entry, cap at 5 ---
    new_entry = {
        "review_id": new_review_id,
        "photo_url": new_review["photo_urls"][0],
        "created_at": new_review["created_at"],
    }
    s["recent_review_photos"] = ([new_entry] + (s.get("recent_review_photos") or []))[:5]

    return s
