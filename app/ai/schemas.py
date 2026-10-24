"""Structured output the model must return. Anything else is rejected."""
from typing import Literal

from pydantic import BaseModel, Field


class DraftClaim(BaseModel):
    statement: str = Field(description="One factual sentence from the response")
    record_id: str | None = None
    field: str | None = None
    value: str | None = None


class Draft(BaseModel):
    evidence_types: list[str]
    response_text: str
    claims: list[DraftClaim]
    recommendation: Literal["FIGHT", "ACCEPT", "ESCALATE"]
    reason: str
