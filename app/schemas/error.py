"""Error response schema."""

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    detail: str
    code: str
