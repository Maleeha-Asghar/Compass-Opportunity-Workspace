import re
from enum import StrEnum
from typing import Any


class OpportunityTypeIntent(StrEnum):
    INTERNSHIP = "internship"
    MASTERS = "masters"
    MIXED = "mixed"

OPPORTUNITY_WORDS = {
    "find",
    "fully",
    "funded",
    "scholarship",
    "scholarships",
    "internship",
    "internships",
    "masters",
    "master",
    "master's",
    "msc",
    "phd",
    "doctoral",
    "fellowship",
    "fellowships",
    "program",
    "programs",
    "programme",
    "programmes",
    "opportunity",
    "opportunities",
    "students",
    "student",
    "for",
    "in",
    "or",
    "and",
    "the",
    "a",
    "an",
    "with",
    "about",
    "looking",
    "seeking",
    "related",
    "research",
    "assistantship",
    "assistantships",
}

SHORT_ALLOWLIST = {"ai", "ml", "cv", "uk", "us", "eu"}

GEO_DEMO_TERMS = {
    "europe",
    "european",
    "asia",
    "asian",
    "africa",
    "african",
    "america",
    "american",
    "pakistan",
    "pakistani",
    "germany",
    "german",
    "canada",
    "canadian",
    "international",
    "global",
    "worldwide",
    "abroad",
    "overseas",
    "foreign",
    "national",
    "nationals",
    "citizen",
    "citizens",
}

LOCATION_ALIASES = {
    "pakistan": {"pakistan"},
    "germany": {"germany"},
    "canada": {"canada"},
    "united states": {"united states", "usa", "u.s.", "us", "america"},
    "usa": {"united states", "usa", "u.s.", "us", "america"},
    "uk": {"united kingdom", "uk", "u.k.", "england", "scotland", "wales"},
    "united kingdom": {"united kingdom", "uk", "u.k.", "england", "scotland", "wales"},
    "australia": {"australia"},
    "france": {"france"},
    "spain": {"spain"},
    "italy": {"italy"},
    "netherlands": {"netherlands"},
    "sweden": {"sweden"},
    "norway": {"norway"},
    "finland": {"finland"},
    "denmark": {"denmark"},
    "europe": {"europe"},
}

REGION_COUNTRIES = {
    "europe": {
        "austria",
        "belgium",
        "denmark",
        "finland",
        "france",
        "germany",
        "ireland",
        "italy",
        "netherlands",
        "norway",
        "poland",
        "portugal",
        "spain",
        "sweden",
        "switzerland",
        "united kingdom",
        "uk",
    }
}


def extract_intent_terms(user_query: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z\-']*", user_query.lower())
    terms: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token in OPPORTUNITY_WORDS:
            continue
        if len(token) < 3 and token not in SHORT_ALLOWLIST:
            continue
        if len(token) < 4 and token not in SHORT_ALLOWLIST:
            continue
        if token in seen:
            continue
        seen.add(token)
        terms.append(token)
    return terms


def extract_topic_terms(user_query: str) -> list[str]:
    return [term for term in extract_intent_terms(user_query) if term not in GEO_DEMO_TERMS]


def extract_location_intents(user_query: str) -> list[str]:
    lowered = " ".join(user_query.lower().split())
    locations: list[str] = []
    for canonical, aliases in LOCATION_ALIASES.items():
        for alias in aliases:
            escaped = re.escape(alias)
            if re.search(rf"\b(in|within|inside|located in|based in)\s+(the\s+)?{escaped}\b", lowered):
                locations.append(canonical)
                break
    return _unique(locations)


def detect_opportunity_type_intent(user_query: str) -> OpportunityTypeIntent:
    lowered = user_query.lower()
    has_internship = bool(re.search(r"\binternships?\b", lowered))
    has_masters = bool(
        re.search(r"\b(masters?|master's|msc|m\.sc|postgraduate|grad(?:uate)?\s+program(?:me)?)\b", lowered)
    )
    if has_internship and has_masters:
        return OpportunityTypeIntent.MIXED
    if has_internship:
        return OpportunityTypeIntent.INTERNSHIP
    if has_masters:
        return OpportunityTypeIntent.MASTERS
    return OpportunityTypeIntent.MIXED


def matches_opportunity_type_intent(intent: OpportunityTypeIntent, opportunity: dict[str, Any]) -> bool:
    if intent == OpportunityTypeIntent.MIXED:
        return True
    blob = opportunity_text(opportunity)
    opportunity_type = str(opportunity.get("opportunity_type") or "").lower()
    if intent == OpportunityTypeIntent.INTERNSHIP:
        return any(token in blob or token in opportunity_type for token in ("internship", "intern", "placement", "co-op"))
    if intent == OpportunityTypeIntent.MASTERS:
        return any(
            token in blob or token in opportunity_type
            for token in ("master", "masters", "msc", "m.sc", "postgraduate", "graduate degree", "ma ", "ms ")
        )
    return True


def opportunity_text(opportunity: dict[str, Any]) -> str:
    parts = [
        opportunity.get("title"),
        opportunity.get("summary"),
        opportunity.get("provider"),
        opportunity.get("opportunity_type"),
        opportunity.get("field"),
        " ".join(opportunity.get("eligibility") or []),
    ]
    return " ".join(str(part) for part in parts if part).lower()


def matches_location_intent(user_query: str, opportunity: dict[str, Any]) -> bool:
    locations = extract_location_intents(user_query)
    if not locations:
        return True
    country = str(opportunity.get("country") or "").strip().lower()
    blob = opportunity_text(opportunity)
    for location in locations:
        aliases = LOCATION_ALIASES.get(location, {location})
        region_countries = REGION_COUNTRIES.get(location, set())
        if country:
            if country in aliases or country in region_countries:
                return True
            return False
        if any(alias in blob for alias in aliases) or any(region_country in blob for region_country in region_countries):
            return True
    return False


def is_opportunity_relevant(user_query: str, opportunity: dict[str, Any]) -> bool:
    terms = extract_topic_terms(user_query)
    if not terms:
        return True
    blob = opportunity_text(opportunity)
    if not blob.strip():
        return True
    return any(term in blob for term in terms)


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            output.append(value)
    return output
