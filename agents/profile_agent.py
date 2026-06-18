import re

from app.config import Settings, get_settings
from schemas.profile_schema import StudentProfile
from tools.groq_tool import GroqClient


class ProfileAgent:
    COUNTRY_PATTERN = re.compile(r"\bfrom\s+([A-Z][A-Za-z ]+?)(?:\s+with|\s+and|\.|,|$)")
    CGPA_PATTERN = re.compile(
        r"(?:\b(?:cgpa|gpa)\s*(?:is|:)?\s*([0-4](?:\.\d{1,2})?)\b)|(?:\b([0-4](?:\.\d{1,2})?)\s*(?:cgpa|gpa)\b)",
        re.IGNORECASE,
    )

    FIELD_KEYWORDS = {
        "data science": "Data Science",
        "computer science": "Computer Science",
        "artificial intelligence": "Artificial Intelligence",
        "ai": "Artificial Intelligence",
        "machine learning": "Machine Learning",
        "ml": "Machine Learning",
    }

    def __init__(self, settings: Settings | None = None, client: GroqClient | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = client or GroqClient(self.settings)

    def update_profile(self, existing: StudentProfile | None, user_text: str) -> StudentProfile:
        base = existing.model_dump() if existing else StudentProfile().model_dump()
        extracted = self._extract_with_llm(user_text, base)
        merged = {**base, **{key: value for key, value in extracted.items() if value not in (None, [], "")}}
        return StudentProfile.model_validate(merged)

    def _extract_with_llm(self, text: str, existing: dict) -> dict:
        system = (
            "You extract student profile facts for Compass. Return strict JSON matching these keys: "
            "full_name, country, degree, field, semester, cgpa, skills, preferred_countries, "
            "preferred_regions, preferred_opportunity_types, budget_preference, ielts_status, "
            "gre_status, career_goal. Use null or [] for unknown values. Do not infer unstated facts."
        )
        payload = self.client.json_chat(
            model=self.settings.fast_model,
            system=system,
            user=f"Existing profile JSON:\n{existing}\n\nStudent message:\n{text}",
            temperature=0.0,
            timeout=self.settings.search_planning_timeout_seconds,
            max_retries=self.settings.search_planning_max_retries,
        )
        return StudentProfile.model_validate(payload).model_dump()

    def _extract(self, text: str) -> dict:
        lowered = text.lower()
        extracted: dict = {}

        country = self.COUNTRY_PATTERN.search(text)
        if country:
            extracted["country"] = country.group(1).strip()

        cgpa = self.CGPA_PATTERN.search(text)
        if cgpa:
            extracted["cgpa"] = float(cgpa.group(1) or cgpa.group(2))

        if "final year" in lowered:
            extracted["semester"] = "Final year"

        degree = self._extract_degree(text)
        if degree:
            extracted["degree"] = degree

        field = self._extract_field(lowered)
        if field:
            extracted["field"] = field

        if "fully funded" in lowered:
            extracted["budget_preference"] = "Fully funded only"

        if "ielts" in lowered:
            extracted["ielts_status"] = "Not taken" if self._not_taken(lowered, "ielts") else "Mentioned"
        if "gre" in lowered:
            extracted["gre_status"] = "Not taken" if self._not_taken(lowered, "gre") else "Mentioned"

        regions = []
        if "europe" in lowered:
            regions.append("Europe")
        extracted["preferred_regions"] = regions

        opportunity_types = []
        for label in ("scholarship", "internship", "fellowship", "assistantship"):
            if label in lowered:
                opportunity_types.append(label.title())
        extracted["preferred_opportunity_types"] = opportunity_types

        countries = [name for name in ("Germany", "Italy", "UK", "Canada", "United States") if name.lower() in lowered]
        extracted["preferred_countries"] = countries

        skills = [name for name in ("Python", "Machine Learning", "LangChain", "LangGraph", "Data Science") if name.lower() in lowered]
        extracted["skills"] = skills

        if any(term in lowered for term in ("master", "research", "career goal")):
            extracted["career_goal"] = text.strip()

        return extracted

    @staticmethod
    def _extract_degree(text: str) -> str | None:
        match = re.search(
            r"\b(BS|MS|MSc|BSc|Bachelor'?s|Master'?s)\s+([A-Za-z ]+?)(?:\s+student|\s+from|\s+with|,|\.|$)",
            text,
            re.IGNORECASE,
        )
        if not match:
            return None
        return " ".join(f"{match.group(1)} {match.group(2)}".split())

    def _extract_field(self, lowered: str) -> str | None:
        for keyword, label in self.FIELD_KEYWORDS.items():
            if keyword in lowered:
                return label
        return None

    @staticmethod
    def _not_taken(text: str, exam: str) -> bool:
        return (
            f"not taken {exam}" in text
            or f"not take {exam}" in text
            or f"no {exam}" in text
            or f"haven't taken {exam}" in text
            or f"have not taken {exam}" in text
        )
