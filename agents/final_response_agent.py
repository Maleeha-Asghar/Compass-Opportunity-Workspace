from typing import Any


class FinalResponseAgent:
    def profile_updated(self, profile: dict[str, Any], queries: list[str]) -> str:
        field = profile.get("field") or "your target field"
        return (
            f"Profile updated for {field}. I also prepared {len(queries)} date-aware "
            "search queries for the current and next application cycles."
        )

    def search_results(self, opportunities: list[dict[str, Any]]) -> str:
        if not opportunities:
            return "No confirmed non-expired opportunities were found yet. Try broadening the query or adding profile details."
        return f"Found {len(opportunities)} opportunity candidates with source tiers and extraction status attached."

    def unsupported(self, intent: str) -> str:
        return f"The {intent} workflow is scaffolded but not implemented in this phase yet."
