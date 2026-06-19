"""Enum (Literal) vocabularies for review fields.

These Literal aliases are the single source of truth shared by the Pydantic
request/response models. Validation is enforced by Pydantic at the model
boundary, so the iOS client and backend stay locked to the same words.
"""

from typing import Literal

AccessLevel = Literal["Easy", "Moderate", "Difficult"]
CrowdLevel = Literal["Empty", "Light", "Moderate", "Crowded"]
BestTimeOfDay = Literal["Sunrise", "GoldenHour", "BlueHour", "Midday", "Night"]
Season = Literal["Spring", "Summer", "Fall", "Winter", "YearRound"]

# Sort modes for the spot review feed + search. "scout" is the quality-blend
# ranking (see _scout_score in review_service); the rest are self-explanatory.
ReviewSort = Literal["newest", "highest_rated", "lowest_rated", "scout"]
