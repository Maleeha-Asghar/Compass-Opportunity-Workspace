from datetime import date
from typing import Any

from app.config import Settings, get_settings
from tools.groq_tool import GroqClient
from tools.search_intent import OpportunityTypeIntent, detect_opportunity_type_intent


class SearchPlannerAgent:
    def __init__(self, settings: Settings | None = None, client: GroqClient | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = client or GroqClient(self.settings)

    def plan(
        self,
        profile: dict[str, Any],
        today: date | None = None,
        user_query: str | None = None,
    ) -> list[str]:
        today = today or date.today()
        current_year = today.year
        next_year = current_year + 1
        request = " ".join(str(user_query or "").split())
        type_intent = detect_opportunity_type_intent(request)
        type_instruction = {
            OpportunityTypeIntent.INTERNSHIP: "Return only internship, research internship, placement, or co-op opportunities.",
            OpportunityTypeIntent.MASTERS: "Return only masters, MSc, MA, or postgraduate degree scholarship/program opportunities.",
            OpportunityTypeIntent.MIXED: "You may mix internships, masters scholarships, fellowships, and research programs.",
        }[type_intent]
        system = (
            "You create web search queries for real scholarships, internships, fellowships, "
            "research internships, and assistantships. Return strict JSON: {\"queries\": [\"...\"]}. "
            "The queries value must be an array of plain search strings only, not objects. "
            "Generate exactly 5 queries. Use only the current and next application cycle years provided. "
            "The student's search request is the PRIMARY intent. Every query must reflect the field, topic, "
            "opportunity type, and constraints in that request. Use profile JSON only for supplemental context "
            "such as nationality, preferred countries, or degree level. Never replace the requested field of study "
            "or topic with a different one from the profile. Target official university and government pages "
            "(site:.edu, site:.ac.uk, site:.gov, official university scholarship pages). Avoid Reddit, forums, "
            "blogs, and scholarship aggregators. Do not invent facts."
        )
        payload = self.client.json_chat(
            model=self.settings.fast_model,
            system=system,
            user=(
                f"Today's date: {today.isoformat()}\n"
                f"Allowed cycle years: {current_year}, {next_year}\n"
                f"Opportunity type focus: {type_intent.value}\n"
                f"Type rule: {type_instruction}\n"
                f"Student search request (PRIMARY):\n{request or 'Not provided'}\n"
                f"Student profile JSON (secondary context):\n{profile}"
            ),
            temperature=0.0,
            timeout=self.settings.search_planning_timeout_seconds,
            max_retries=self.settings.search_planning_max_retries,
        )
        queries = payload.get("queries", [])
        if not isinstance(queries, list):
            raise ValueError("Search planner must return a queries array.")
        normalized = self._normalize_queries(queries)
        if len(normalized) != 5:
            raise ValueError("Search planner must return exactly 5 queries.")
        return self._anchor_user_request(request, normalized, today, detect_opportunity_type_intent(request))

    @classmethod
    def _anchor_user_request(
        cls,
        user_query: str,
        queries: list[str],
        today: date,
        type_intent: OpportunityTypeIntent,
    ) -> list[str]:
        request = " ".join(user_query.split())
        if not request:
            return queries
        anchors = [
            f"{request} site:.edu official",
            f"{request} official application deadline {today.year} site:.edu",
        ]
        if type_intent == OpportunityTypeIntent.INTERNSHIP:
            anchors.append(f"{request} university internship site:.edu {today.year}")
        elif type_intent == OpportunityTypeIntent.MASTERS:
            anchors.append(f"{request} masters scholarship program site:.edu {today.year}")
        else:
            anchors.append(f"{request} scholarship internship site:.edu {today.year}")
        anchored = cls._unique([*anchors, request, *queries])
        return anchored[: len(queries)]

    @classmethod
    def _normalize_queries(cls, queries: list[Any]) -> list[str]:
        output: list[str] = []
        for item in queries:
            query = cls._coerce_query(item)
            if query:
                output.append(query)
        return cls._unique(output)

    @staticmethod
    def _coerce_query(value: Any) -> str | None:
        if isinstance(value, str):
            query = " ".join(value.split())
            return query or None
        if isinstance(value, dict):
            for key in ("query", "q", "text", "search_query"):
                raw = value.get(key)
                if raw:
                    query = " ".join(str(raw).split())
                    return query or None
        return None

    @staticmethod
    def _first(value: Any) -> str | None:
        if isinstance(value, list) and value:
            return str(value[0])
        if isinstance(value, str) and value:
            return value
        return None

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for value in values:
            normalized = " ".join(value.split())
            key = normalized.lower()
            if normalized and key not in seen:
                seen.add(key)
                output.append(normalized)
        return output
