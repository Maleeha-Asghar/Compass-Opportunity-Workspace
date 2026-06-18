from rapidfuzz import fuzz


class DeduplicationEngine:
    def merge(self, candidates: list[dict]) -> list[dict]:
        merged: list[dict] = []
        for candidate in candidates:
            duplicate = self._find_duplicate(candidate, merged)
            if duplicate is None:
                merged.append(candidate)
                continue
            self._merge_into(duplicate, candidate)
        return merged

    def _find_duplicate(self, candidate: dict, existing: list[dict]) -> dict | None:
        for item in existing:
            if candidate.get("application_url") and candidate.get("application_url") == item.get("application_url"):
                return item
            title_score = fuzz.token_sort_ratio(
                str(candidate.get("title", "")).lower(),
                str(item.get("title", "")).lower(),
            )
            provider_score = fuzz.token_sort_ratio(
                str(candidate.get("provider", "")).lower(),
                str(item.get("provider", "")).lower(),
            )
            if title_score > 85 and provider_score > 80:
                return item
        return None

    @staticmethod
    def _merge_into(canonical: dict, incoming: dict) -> None:
        notes = canonical.setdefault("extraction_notes", [])
        for field in ("deadline", "funding_type"):
            if canonical.get(field) and incoming.get(field) and canonical[field] != incoming[field]:
                notes.append(f"{field} differs across sources: {canonical[field]} vs {incoming[field]}.")
        for key, value in incoming.items():
            if key not in canonical or canonical[key] in (None, "", []):
                canonical[key] = value
        canonical.setdefault("merged_sources", []).append(
            {
                "application_url": incoming.get("application_url"),
                "source_tier": incoming.get("source_tier"),
            }
        )
