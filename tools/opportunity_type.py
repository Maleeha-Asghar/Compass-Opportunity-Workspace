from __future__ import annotations

from typing import Any


CANONICAL_OPPORTUNITY_TYPES = {
    "masters",
    "internship",
    "scholarship",
    "fellowship",
    "assistantship",
    "research",
    "other",
}


def normalize_opportunity_type(opportunity: dict[str, Any], user_query: str | None = None) -> str:
    text = " ".join(
        str(value)
        for value in (
            opportunity.get("opportunity_type"),
            opportunity.get("title"),
            opportunity.get("summary"),
            opportunity.get("funding_type"),
            user_query,
            " ".join(opportunity.get("eligibility") or []),
        )
        if value
    ).lower()
    explicit = str(opportunity.get("opportunity_type") or "").strip().lower().replace(" ", "_")
    if explicit == "internship":
        return "internship"
    if explicit == "masters":
        return "masters"
    if any(term in text for term in ("internship", "intern ", "traineeship", "placement", "co-op", "cooperative education")):
        return "internship"
    if any(
        term in text
        for term in (
            "masters",
            "master's",
            "master of",
            "master ",
            "msc",
            "m.sc",
            "ms program",
            "graduate degree",
            "postgraduate",
        )
    ):
        return "masters"
    if "assistantship" in text:
        return "assistantship"
    if "fellowship" in text:
        return "fellowship"
    if "scholarship" in text:
        return "scholarship"
    if any(term in text for term in ("research program", "summer research", "research opportunity")):
        return "research"
    return "other"


def opportunity_display_group(opportunity_type: str | None) -> str:
    if opportunity_type == "internship":
        return "internships"
    if opportunity_type == "masters":
        return "masters"
    return "other"
