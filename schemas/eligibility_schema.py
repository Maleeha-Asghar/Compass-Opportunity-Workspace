from pydantic import BaseModel, Field


class EligibilityResult(BaseModel):
    eligible: bool
    score: float = Field(ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    deadline_passed: bool = False
