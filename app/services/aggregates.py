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
        "crowd_level_counts": {},
        "mode_access_level": None,
        "mode_crowd_level": None,
        # entrance_fee is a money number → running average, not a mode.
        "entrance_fee_sum": 0.0,
        "entrance_fee_n": 0,
        "avg_entrance_fee": None,
        "recent_review_photos": [],
        "best_time_of_day_counts": {},
        "best_times": [],
        "best_season_counts": {},
        "best_seasons": [],
        "permit_required_counts": {},
        "drone_allowed_counts": {},
        "tripod_allowed_counts": {},
        "mode_permit_required": None,
        "mode_drone_allowed": None,
        "mode_tripod_allowed": None,
        "recent_gear_recommendations": [],
        "recent_composition_hints": [],
    }


def _get_boolean_mode(counts: dict, tie_breaker: bool) -> bool | None:
    """
    Majority vote for tristate booleans stored as 'true'/'false' keys.

    Returns None when nobody answered (unanswered ≠ "no"). Once there are real
    answers, ties fall back to the deterministic tie_breaker.
    """
    true_count = counts.get("true", 0)
    false_count = counts.get("false", 0)
    if true_count == 0 and false_count == 0:
        return None
    if true_count == false_count:
        return tie_breaker
    return true_count > false_count


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

    # --- single-value mode fields via running counts ---
    # Unanswered (None) isn't a vote: skip it so the existing mode is preserved.
    for field in ("access_level", "crowd_level"):
        v = new_review.get(field)
        if v is None:
            continue
        counts_key = f"{field}_counts"
        counts = dict(s.get(counts_key) or {})
        counts[v] = counts.get(v, 0) + 1
        s[counts_key] = counts
        # Deterministic tie-break: highest count, then alphabetical
        s[f"mode_{field}"] = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

    # --- entrance_fee running average (money number, not a mode) ---
    # 0.00 (free) is a real data point and counts; None (unanswered) is skipped.
    fee = new_review.get("entrance_fee")
    if fee is not None:
        s["entrance_fee_n"] = s.get("entrance_fee_n", 0) + 1
        s["entrance_fee_sum"] = s.get("entrance_fee_sum", 0.0) + fee
        s["avg_entrance_fee"] = round(s["entrance_fee_sum"] / s["entrance_fee_n"], 2)

    # --- multi-value aggregations (best_time_of_day, best_season) ---
    for field, list_key in (
        ("best_time_of_day", "best_times"),
        ("best_season", "best_seasons"),
    ):
        counts_key = f"{field}_counts"
        counts = dict(s.get(counts_key) or {})
        for val in new_review.get(field) or []:
            counts[val] = counts.get(val, 0) + 1
        s[counts_key] = counts
        s[list_key] = [
            item[0]
            for item in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
            if item[1] > 0
        ]

    # --- access & logistics tristate boolean aggregation ---
    # Unanswered (None) isn't a vote: skip it so the existing mode is preserved.
    for field, tie_breaker in [
        ("permit_required", True),
        ("drone_allowed", False),
        ("tripod_allowed", False),
    ]:
        val = new_review.get(field)
        if val is None:
            continue
        counts_key = f"{field}_counts"
        counts = dict(s.get(counts_key) or {})
        val_str = "true" if val else "false"
        counts[val_str] = counts.get(val_str, 0) + 1
        s[counts_key] = counts
        s[f"mode_{field}"] = _get_boolean_mode(counts, tie_breaker)

    # --- gear & composition textual aggregates ---
    gear_tips = list(s.get("recent_gear_recommendations") or [])
    new_gear = new_review.get("gear_recommendations") or ""
    if new_gear.strip():
        gear_tips = [new_gear.strip()] + gear_tips
        s["recent_gear_recommendations"] = gear_tips[:5]

    comp_tips = list(s.get("recent_composition_hints") or [])
    new_comp = new_review.get("composition_hints") or ""
    if new_comp.strip():
        comp_tips = [new_comp.strip()] + comp_tips
        s["recent_composition_hints"] = comp_tips[:5]

    # --- recent_review_photos: prepend new entry, cap at 5 ---
    new_entry = {
        "review_id": new_review_id,
        "photo_url": new_review["photo_urls"][0],
        "created_at": new_review["created_at"],
    }
    s["recent_review_photos"] = ([new_entry] + (s.get("recent_review_photos") or []))[:5]

    return s
