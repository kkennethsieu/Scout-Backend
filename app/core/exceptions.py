"""Domain error hierarchy — consistent {detail, code} JSON responses."""


class DomainError(Exception):
    """Base class for all domain errors. Caught by the global handler in main.py."""

    def __init__(self, status: int, code: str, detail: str, payload: dict | None = None):
        self.status = status
        self.code = code
        self.detail = detail
        self.payload = payload or {}


class SpotNotFound(DomainError):
    def __init__(self):
        super().__init__(404, "SPOT_NOT_FOUND", "Spot not found")


class ReviewNotFound(DomainError):
    def __init__(self):
        super().__init__(404, "REVIEW_NOT_FOUND", "Review not found")


class ListNotFound(DomainError):
    def __init__(self):
        super().__init__(404, "LIST_NOT_FOUND", "List not found")


class FavoritesProtected(DomainError):
    def __init__(self):
        super().__init__(
            400,
            "FAVORITES_PROTECTED",
            "The Favorites list cannot be renamed or deleted.",
        )


class ListLimitReached(DomainError):
    def __init__(self, limit: int):
        super().__init__(400, "LIST_LIMIT_REACHED", f"You can have at most {limit} lists.")


class UserNotFound(DomainError):
    def __init__(self):
        super().__init__(404, "USER_NOT_FOUND", "User not found")


class PhotoInvalidFormat(DomainError):
    def __init__(self):
        super().__init__(400, "PHOTO_INVALID_FORMAT", "Photo must be a valid JPEG")


class PhotoTooLarge(DomainError):
    def __init__(self):
        super().__init__(400, "PHOTO_TOO_LARGE", "Photo exceeds size limit")


class PhotoCountInvalid(DomainError):
    def __init__(self):
        super().__init__(400, "PHOTO_COUNT_INVALID", "Must include 1–10 photos")


class InvalidEnumValue(DomainError):
    def __init__(self, field: str, value: str):
        super().__init__(400, "INVALID_ENUM_VALUE", f"Invalid value '{value}' for {field}")


class InvalidCursor(DomainError):
    def __init__(self):
        super().__init__(400, "INVALID_CURSOR", "Pagination cursor is invalid")


class GeocodingFailed(DomainError):
    def __init__(self, reason: str = ""):
        detail = f"Geocoding failed: {reason}".strip(": ").strip()
        if detail == "Geocoding failed":
            detail = "Geocoding failed"
        super().__init__(503, "GEOCODING_FAILED", detail)


class GeocodingNoLocation(DomainError):
    def __init__(self):
        super().__init__(
            422,
            "GEOCODING_NO_LOCATION",
            "Could not resolve a city/country for this location.",
        )


class MissingToken(DomainError):
    def __init__(self):
        super().__init__(401, "MISSING_TOKEN", "Authorization header missing or malformed")


class InvalidToken(DomainError):
    def __init__(self):
        super().__init__(401, "INVALID_TOKEN", "Token is invalid or expired")


class UpstreamUnavailable(DomainError):
    def __init__(self):
        super().__init__(503, "UPSTREAM_UNAVAILABLE", "Upstream service unavailable")


class InternalError(DomainError):
    def __init__(self):
        super().__init__(500, "INTERNAL_ERROR", "Internal server error")


class Forbidden(DomainError):
    def __init__(self, detail: str = "You do not have permission to perform this action"):
        super().__init__(403, "FORBIDDEN", detail)


class ReviewAlreadyExists(DomainError):
    def __init__(self, spot_id: str, review_id: str):
        super().__init__(
            status=409,
            code="REVIEW_ALREADY_EXISTS",
            detail="You have already reviewed this spot.",
            payload={
                "spot_id": spot_id,
                "review_id": review_id,
            },
        )


class SpotAlreadyExists(DomainError):
    def __init__(self, spot_id: str, name: str, distance_m: float):
        super().__init__(
            status=409,
            code="SPOT_ALREADY_EXISTS",
            detail=f"A spot named '{name}' already exists nearby ({int(distance_m)}m away).",
            payload={
                "spot_id": spot_id,
                "name": name,
                "distance_m": distance_m,
            },
        )
