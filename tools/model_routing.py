import re
from enum import StrEnum


class ModelTask(StrEnum):
    OPPORTUNITY = "opportunity"
    DEADLINE = "deadline"
    TABLE = "table"
    VERIFICATION = "verification"
    ELIGIBILITY = "eligibility"


DATE_KEYWORDS = (
    "deadline",
    "due date",
    "apply by",
    "closes on",
    "closing date",
    "application period",
    "last day to apply",
)
MONTH_PATTERN = re.compile(
    r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b",
    re.IGNORECASE,
)
ISO_DATE_PATTERN = re.compile(r"\b20\d{2}[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\b")
YEAR_PATTERN = re.compile(r"\b20\d{2}\b")


def has_date_signals(text: str) -> bool:
    if not text.strip():
        return False
    lowered = text.lower()
    if any(keyword in lowered for keyword in DATE_KEYWORDS):
        return True
    if ISO_DATE_PATTERN.search(text):
        return True
    if MONTH_PATTERN.search(text) and YEAR_PATTERN.search(text):
        return True
    return False
