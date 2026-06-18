from pydantic import BaseModel, Field


class GeneratedDocument(BaseModel):
    opportunity_id: str | None = None
    document_type: str
    content: str
    grounding_flags: list[str] = Field(default_factory=list)
