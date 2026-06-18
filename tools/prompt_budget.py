import re

FOCUS_KEYWORDS = (
    "deadline",
    "apply",
    "application",
    "eligibility",
    "requirement",
    "funding",
    "scholarship",
    "stipend",
    "tuition",
    "documents",
    "contact",
    "email",
    "fully funded",
    "international",
    "pakistan",
    "pakistani",
)


def truncate_text(text: str, max_chars: int) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars]


def focus_text(text: str, max_chars: int, keywords: tuple[str, ...] = FOCUS_KEYWORDS) -> str:
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return ""
    if len(cleaned) <= max_chars:
        return cleaned

    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    if len(sentences) <= 1:
        return cleaned[:max_chars]

    scored: list[tuple[int, int, str]] = []
    for index, sentence in enumerate(sentences):
        lowered = sentence.lower()
        score = sum(1 for keyword in keywords if keyword in lowered)
        scored.append((score, index, sentence))

    scored.sort(key=lambda item: (-item[0], item[1]))
    picked: list[str] = []
    total = 0
    for _, _, sentence in scored:
        next_total = total + len(sentence) + (1 if picked else 0)
        if next_total > max_chars:
            continue
        picked.append(sentence)
        total = next_total

    if not picked:
        return cleaned[:max_chars]
    return " ".join(picked)[:max_chars]


def slim_opportunity(opportunity: dict, *, summary_chars: int = 400) -> dict:
    summary = opportunity.get("summary")
    return {
        "title": opportunity.get("title"),
        "provider": opportunity.get("provider"),
        "country": opportunity.get("country"),
        "opportunity_type": opportunity.get("opportunity_type"),
        "deadline": opportunity.get("deadline"),
        "funding_type": opportunity.get("funding_type"),
        "eligibility": (opportunity.get("eligibility") or [])[:8],
        "required_documents": (opportunity.get("required_documents") or [])[:8],
        "application_url": opportunity.get("application_url"),
        "contact_email": opportunity.get("contact_email"),
        "summary": truncate_text(str(summary or ""), summary_chars) or None,
        "payment_requested": opportunity.get("payment_requested"),
        "warnings": (opportunity.get("warnings") or [])[:5],
    }


def slim_candidate(candidate: dict, *, snippet_chars: int = 350) -> dict:
    return {
        "source_url": candidate.get("source_url"),
        "source_title": candidate.get("source_title"),
        "title": candidate.get("title"),
        "snippet": truncate_text(str(candidate.get("snippet") or ""), snippet_chars),
        "content_type": candidate.get("content_type"),
        "source_tier": candidate.get("source_tier"),
        "domain": candidate.get("domain"),
    }


def slim_profile(profile: dict) -> dict:
    return {key: value for key, value in profile.items() if value not in (None, "", [], {})}
