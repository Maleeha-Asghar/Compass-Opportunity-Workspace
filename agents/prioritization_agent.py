from app.config import Settings, get_settings
from tools.groq_tool import GroqClient
from tools.search_intent import (
    detect_opportunity_type_intent,
    extract_topic_terms,
    is_opportunity_relevant,
    matches_location_intent,
    matches_opportunity_type_intent,
)


class PrioritizationAgent:
    TRUST_WEIGHT = {"trusted": 0.25, "needs_review": 0.1, "suspicious": -0.35}
    TIER_WEIGHT = {"A": 0.2, "B": 0.18, "C": 0.02, "D": -0.5}

    def __init__(self, settings: Settings | None = None, client: GroqClient | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = client or GroqClient(self.settings)

    def rank(self, opportunities: list[dict], user_query: str | None = None) -> list[dict]:
        if not opportunities:
            return []
        try:
            return self._rank_with_model(opportunities, user_query=user_query)
        except Exception:
            return self._heuristic_rank(opportunities, user_query=user_query)

    def _rank_with_model(self, opportunities: list[dict], user_query: str | None = None) -> list[dict]:
        request = " ".join(str(user_query or "").split())
        system = (
            "Rank opportunities for a student-facing Compass result list. Return strict JSON only: "
            "{\"ranked\": [{\"index\": 0, \"priority_score\": 0.0, \"priority\": \"high|medium|low\", \"ranking_reason\": \"...\"}]}. "
            "Relevance to the student's search request is the top factor. Deprioritize opportunities in unrelated fields. "
            "Then use eligibility, trust, funding, deadline urgency, source tier, and suspicious flags. "
            "Keep original indexes. No markdown fences or commentary."
        )
        payload = self.client.json_chat(
            model=self.settings.fast_model,
            system=system,
            user=(
                f"Student search request:\n{request or 'Not provided'}\n"
                f"Opportunities JSON array:\n{opportunities}"
            ),
            temperature=0.0,
            timeout=self.settings.search_extraction_timeout_seconds,
            max_retries=self.settings.search_extraction_max_retries,
        )
        by_index = {int(item["index"]): item for item in payload.get("ranked", []) if "index" in item}
        ranked = []
        for index, opportunity in enumerate(opportunities):
            model_rank = by_index.get(index, {})
            score = max(
                0.0,
                min(1.0, float(model_rank.get("priority_score", self._score(opportunity, user_query=user_query)))),
            )
            priority = model_rank.get("priority") or self._priority_label(score)
            ranked.append(
                {
                    **opportunity,
                    "priority_score": round(score, 3),
                    "priority": priority,
                    "ranking_reason": model_rank.get("ranking_reason"),
                }
            )
        return sorted(ranked, key=lambda item: item["priority_score"], reverse=True)

    def _heuristic_rank(self, opportunities: list[dict], user_query: str | None = None) -> list[dict]:
        ranked = []
        for opportunity in opportunities:
            score = self._score(opportunity, user_query=user_query)
            ranked.append(
                {
                    **opportunity,
                    "priority_score": round(score, 3),
                    "priority": self._priority_label(score),
                    "ranking_reason": "Heuristic rank after model ranking was unavailable.",
                }
            )
        return sorted(ranked, key=lambda item: item["priority_score"], reverse=True)

    @staticmethod
    def _priority_label(score: float) -> str:
        if score >= 0.75:
            return "high"
        if score >= 0.45:
            return "medium"
        return "low"

    def _score(self, opportunity: dict, user_query: str | None = None) -> float:
        eligibility = opportunity.get("eligibility_result") or {}
        verification = opportunity.get("verification") or {}
        score = float(eligibility.get("score", 0.4))
        score += self.TRUST_WEIGHT.get(verification.get("trust_level"), 0)
        score += self.TIER_WEIGHT.get(opportunity.get("source_tier"), 0)
        if opportunity.get("payment_requested"):
            score -= 0.3
        if user_query:
            terms = extract_topic_terms(user_query)
            if terms and is_opportunity_relevant(user_query, opportunity):
                score += 0.2
            elif terms:
                score -= 0.35
            type_intent = detect_opportunity_type_intent(user_query)
            if matches_opportunity_type_intent(type_intent, opportunity):
                score += 0.15
            elif type_intent.value != "mixed":
                score -= 0.3
            if matches_location_intent(user_query, opportunity):
                score += 0.15
            else:
                score -= 0.45
        return max(0.0, min(1.0, score))
