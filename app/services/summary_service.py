"""AI review summaries — a short "what photographers say" blurb per spot.

Generated with Google Gemini from a spot's reviews, stored denormalized on the
spot doc, and refreshed in the background after writes (debounced — only once a
spot accrues AI_SUMMARY_REFRESH_EVERY new reviews since the last summary).

The four ai_summary* fields live on the spot doc OUTSIDE the incremental
aggregate machinery (they're expensive, not additive). delete_review preserves
them across its aggregate rebuild; see review_service._SPOT_IDENTITY_FIELDS.

maybe_regenerate_summary is the fire-and-forget entry point scheduled via
FastAPI BackgroundTasks — it must never raise.
"""

import logging
from datetime import datetime, timezone

from app.core.config import settings
from app.core.firebase import db
from app.services import review_service, spot_cache

log = logging.getLogger(__name__)

# Cap how many reviews feed the prompt — bounds token cost on popular spots.
# _load_spot_reviews returns newest-first, so this keeps the most recent N.
_MAX_REVIEWS_IN_PROMPT = 30
# Keep the output short — it's a 2-3 sentence blurb.
_MAX_OUTPUT_TOKENS = 200

_SYSTEM_INSTRUCTION = (
    "You write concise, neutral summaries of what photographers say about a photo "
    "spot, based ONLY on the reviews provided. Do not invent facts, ratings, gear, "
    "or conditions that aren't in the reviews. Write 2-3 sentences, no preamble, no "
    "lists, no markdown — just the summary text."
)

# Lazily-built Gemini client so import never requires a key.
_client = None


def _get_client():
    """Build (once) and return the Gemini client. Caller guarantees a key exists."""
    global _client
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def _fmt(value) -> str:
    """Render an aggregate value for the prompt, skipping empties."""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def _build_prompt(spot: dict, reviews: list[dict]) -> str:
    """Assemble a compact prompt from the spot's aggregates + review free-text.

    Only the fields a photographer would care about; missing/empty fields are
    skipped so we don't feed Gemini "None".
    """
    lines: list[str] = []
    name = spot.get("name") or "this spot"
    location = ", ".join(
        p for p in (spot.get("city"), spot.get("admin_area"), spot.get("country")) if p
    )
    lines.append(f"Photo spot: {name}" + (f" ({location})" if location else ""))

    # Aggregate context (only what's populated).
    agg_fields = [
        ("Average rating", spot.get("avg_rating")),
        ("Number of reviews", spot.get("review_count")),
        ("Typical access difficulty", spot.get("mode_access_level")),
        ("Typical crowd level", spot.get("mode_crowd_level")),
        ("Best times of day", spot.get("best_times")),
        ("Best seasons", spot.get("best_seasons")),
        ("Average entrance fee (USD)", spot.get("avg_entrance_fee")),
    ]
    for label, value in agg_fields:
        if value is None or value == [] or value == "":
            continue
        lines.append(f"{label}: {_fmt(value)}")

    # Tristate logistics — only mention when answered.
    for label, value in [
        ("Permit usually required", spot.get("mode_permit_required")),
        ("Drones usually allowed", spot.get("mode_drone_allowed")),
        ("Tripods usually allowed", spot.get("mode_tripod_allowed")),
    ]:
        if value is not None:
            lines.append(f"{label}: {'yes' if value else 'no'}")

    lines.append("")
    lines.append("Reviews:")
    for i, r in enumerate(reviews[:_MAX_REVIEWS_IN_PROMPT], start=1):
        parts = [f"rating {r.get('overall_rating')}/5"]
        for field, tag in (
            ("notes", "notes"),
            ("gear_recommendations", "gear"),
            ("composition_hints", "composition"),
        ):
            text = (r.get(field) or "").strip()
            if text:
                parts.append(f"{tag}: {text}")
        lines.append(f"{i}. " + " | ".join(parts))

    lines.append("")
    lines.append("Summarize what photographers say about shooting here in 2-3 sentences.")
    return "\n".join(lines)


def _generate(prompt: str) -> str:
    """Call Gemini and return the trimmed summary text (may raise — caller guards)."""
    from google.genai import types

    client = _get_client()
    resp = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTION,
            max_output_tokens=_MAX_OUTPUT_TOKENS,
            temperature=0.4,
        ),
    )
    return (resp.text or "").strip()


def _is_due(spot: dict) -> bool:
    """True if this spot qualifies for a (re)generated summary right now."""
    review_count = spot.get("review_count", 0)
    if review_count < settings.AI_SUMMARY_MIN_REVIEWS:
        return False
    # No summary yet → due. Otherwise debounce on review-count growth.
    if not spot.get("ai_summary"):
        return True
    last = spot.get("ai_summary_review_count") or 0
    return (review_count - last) >= settings.AI_SUMMARY_REFRESH_EVERY


def maybe_regenerate_summary(spot_id: str | None) -> None:
    """Fire-and-forget: regenerate a spot's AI summary if it's due.

    Scheduled via BackgroundTasks after review writes. Swallows all errors —
    a summary failure must never surface to the client or crash the worker.
    """
    if not settings.AI_SUMMARIES_ENABLED or not settings.GEMINI_API_KEY or not spot_id:
        return
    try:
        spot_ref = db.collection("spots").document(spot_id)
        snap = spot_ref.get()
        if not snap.exists:
            return
        spot = snap.to_dict() or {}

        if not _is_due(spot):
            return

        reviews = review_service._load_spot_reviews(spot_id)
        if not reviews:
            return

        summary = (_generate(_build_prompt(spot, reviews)) or "").strip()
        if not summary:
            return

        spot_ref.set(
            {
                "ai_summary": summary,
                "ai_summary_review_count": spot.get("review_count", 0),
                "ai_summary_generated_at": datetime.now(timezone.utc),
                "ai_summary_model": settings.GEMINI_MODEL,
            },
            merge=True,
        )
        # Summary changed → drop the cached spots snapshot on this instance.
        spot_cache.invalidate()
    except Exception as e:  # noqa: BLE001 — fire-and-forget, never propagate
        log.error("AI summary regeneration failed for spot %s: %s", spot_id, str(e))
