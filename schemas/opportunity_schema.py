from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl


class SourceTier(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class Opportunity(BaseModel):
    title: str
    provider: str | None = None
    country: str | None = None
    opportunity_type: str | None = None
    deadline: date | None = None
    funding_type: str | None = None
    eligibility: list[str] = Field(default_factory=list)
    required_documents: list[str] = Field(default_factory=list)
    application_url: HttpUrl | None = None
    contact_email: str | None = None
    summary: str | None = None
    payment_requested: bool = False
    warnings: list[str] = Field(default_factory=list)
    extraction_notes: list[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    title: str
    url: HttpUrl
    snippet: str = ""
    source: str = "web"


class CandidateSource(BaseModel):
    url: HttpUrl
    content_type: str
    text: str = ""
    tier: SourceTier
    reason: str | None = None
