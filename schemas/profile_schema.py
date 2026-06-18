from pydantic import BaseModel, Field, field_validator


class StudentProfile(BaseModel):
    full_name: str | None = None
    country: str | None = None
    degree: str | None = None
    field: str | None = None
    semester: str | None = None
    cgpa: float | None = Field(default=None, ge=0, le=4.0)
    skills: list[str] = Field(default_factory=list)
    preferred_countries: list[str] = Field(default_factory=list)
    preferred_regions: list[str] = Field(default_factory=list)
    preferred_opportunity_types: list[str] = Field(default_factory=list)
    budget_preference: str | None = None
    ielts_status: str | None = None
    gre_status: str | None = None
    career_goal: str | None = None

    @field_validator(
        "skills",
        "preferred_countries",
        "preferred_regions",
        "preferred_opportunity_types",
        mode="before",
    )
    @classmethod
    def split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value
