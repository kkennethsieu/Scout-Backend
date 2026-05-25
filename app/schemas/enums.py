"""Enum types and validation helpers for form fields.

FastAPI's Form(...) doesn't enforce Literal types at the framework level,
so we validate explicitly and return 400 INVALID_ENUM_VALUE.
"""

from typing import Literal, get_args

from app.core.exceptions import InvalidEnumValue

AccessLevel = Literal["Easy", "Moderate", "Difficult"]
EntranceFee = Literal["Free", "Paid", "Permit"]
CrowdLevel = Literal["Empty", "Light", "Moderate", "Crowded"]
Environment = Literal["Urban", "Nature", "Coastal", "Mountain", "Desert", "Indoor"]
BestTimeOfDay = Literal["Sunrise", "GoldenHour", "BlueHour", "Midday", "Night"]

# Precompute allowed values for O(1) membership checks
ACCESS_LEVEL_VALUES = set(get_args(AccessLevel))
ENTRANCE_FEE_VALUES = set(get_args(EntranceFee))
CROWD_LEVEL_VALUES = set(get_args(CrowdLevel))
ENVIRONMENT_VALUES = set(get_args(Environment))
BEST_TIME_OF_DAY_VALUES = set(get_args(BestTimeOfDay))

_ENUM_REGISTRY: dict[str, set[str]] = {
    "access_level": ACCESS_LEVEL_VALUES,
    "entrance_fee": ENTRANCE_FEE_VALUES,
    "crowd_level": CROWD_LEVEL_VALUES,
    "environment": ENVIRONMENT_VALUES,
    "best_time_of_day": BEST_TIME_OF_DAY_VALUES,
}


def validate_enum(field: str, value: str) -> str:
    """Validate a single enum value. Raises InvalidEnumValue on failure."""
    allowed = _ENUM_REGISTRY.get(field)
    if allowed is None:
        raise ValueError(f"Unknown enum field: {field}")
    if value not in allowed:
        raise InvalidEnumValue(field, value)
    return value


def validate_enum_list(field: str, values: list[str]) -> list[str]:
    """Validate a list of enum values (e.g., best_time_of_day). Returns validated list."""
    for v in values:
        validate_enum(field, v)
    return values
