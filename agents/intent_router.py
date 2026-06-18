from dataclasses import dataclass


@dataclass(frozen=True)
class IntentDecision:
    intent: str
    confidence: float


class IntentRouter:
    PROFILE_TERMS = {"profile", "cgpa", "degree", "semester", "skills", "ielts", "gre"}
    SEARCH_TERMS = {"scholarship", "internship", "opportunity", "fellowship", "assistantship", "find"}
    DOCUMENT_TERMS = {"sop", "cover letter", "email", "motivation letter", "draft"}
    TRACKER_TERMS = {"track", "status", "applied", "submitted", "application"}
    DEADLINE_TERMS = {"deadline", "plan", "tasks", "reminder"}

    def route(self, user_query: str) -> IntentDecision:
        text = user_query.lower()
        if self._contains_any(text, self.DOCUMENT_TERMS):
            return IntentDecision("draft_document", 0.85)
        if self._contains_any(text, self.TRACKER_TERMS):
            return IntentDecision("track_application", 0.8)
        if self._contains_any(text, self.DEADLINE_TERMS):
            return IntentDecision("deadline_plan", 0.75)
        if self._contains_any(text, self.SEARCH_TERMS):
            return IntentDecision("find_opportunities", 0.85)
        if self._contains_any(text, self.PROFILE_TERMS) or "i am" in text or "i'm" in text:
            return IntentDecision("profile_update", 0.75)
        return IntentDecision("find_opportunities", 0.45)

    @staticmethod
    def _contains_any(text: str, terms: set[str]) -> bool:
        return any(term in text for term in terms)
