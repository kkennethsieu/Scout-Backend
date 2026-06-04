"""Enum (Literal) vocabularies for review fields.

These Literal aliases are the single source of truth shared by the Pydantic
request/response models. Validation is enforced by Pydantic at the model
boundary, so the iOS client and backend stay locked to the same words.
"""

from typing import Literal

AccessLevel = Literal["Easy", "Moderate", "Difficult"]
EntranceFee = Literal["Free", "Paid", "Permit"]
CrowdLevel = Literal["Empty", "Light", "Moderate", "Crowded"]
BestTimeOfDay = Literal["Sunrise", "GoldenHour", "BlueHour", "Midday", "Night"]
Season = Literal["Spring", "Summer", "Fall", "Winter", "YearRound"]
