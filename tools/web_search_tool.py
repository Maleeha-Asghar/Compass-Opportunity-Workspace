from typing import Any

import requests

from app.config import Settings, get_settings
from schemas.opportunity_schema import SearchResult
from tools.observability_tool import timed_api_call
from tools.retry_tool import with_backoff
from tools.source_policy_gate import DENYLIST_DOMAINS
from tools.supabase_tool import SupabaseRepository


class SearchProvider:
    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        raise NotImplementedError


class TavilySearchProvider(SearchProvider):
    def __init__(self, api_key: str, settings: Settings | None = None, repository: SupabaseRepository | None = None) -> None:
        self.api_key = api_key
        self.settings = settings or get_settings()
        self.repository = repository or SupabaseRepository(self.settings)

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        cached = self.repository.get_cached_search_results(query, "tavily")
        if cached is not None:
            return [SearchResult.model_validate(item) for item in cached]
        with timed_api_call(provider="tavily", endpoint="/search", model=None, metadata={"query": query}) as call:
            response = with_backoff(
                lambda: requests.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "max_results": max_results,
                        "search_depth": "advanced",
                        "exclude_domains": sorted(
                            {domain.removeprefix("www.") for domain in DENYLIST_DOMAINS}
                        ),
                    },
                    timeout=20,
                )
            )
            call["status_code"] = response.status_code
            call["success"] = response.ok
            if not response.ok:
                call["error_message"] = response.text[:500]
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        results = [
            SearchResult(
                title=item.get("title") or item.get("url", "Untitled result"),
                url=item["url"],
                snippet=item.get("content", ""),
                source="tavily",
            )
            for item in payload.get("results", [])
            if item.get("url")
        ]
        self.repository.save_search_results_cache(
            query=query,
            provider="tavily",
            results=[item.model_dump(mode="json") for item in results],
            ttl_hours=self.settings.search_cache_ttl_hours,
        )
        return results


def build_search_provider(settings: Settings | None = None) -> SearchProvider:
    settings = settings or get_settings()
    return TavilySearchProvider(settings.require_tavily(), settings=settings)


class TavilyExtractClient:
    def __init__(self, api_key: str, settings: Settings | None = None) -> None:
        self.api_key = api_key
        self.settings = settings or get_settings()

    def extract_url(self, url: str, *, search_query: str | None = None, title: str | None = None) -> str | None:
        query = self._build_query(search_query=search_query, title=title)
        payload: dict[str, Any] = {
            "api_key": self.api_key,
            "urls": url,
            "query": query,
            "chunks_per_source": max(1, min(5, self.settings.tavily_extract_chunks_per_source)),
            "extract_depth": self.settings.tavily_extract_depth,
            "format": "text",
            "timeout": float(max(self.settings.scrape_timeout_seconds, 10)),
        }
        with timed_api_call(
            provider="tavily",
            endpoint="/extract",
            model=None,
            metadata={"url": url, "query": query},
        ) as call:
            response = with_backoff(
                lambda: requests.post(
                    "https://api.tavily.com/extract",
                    json=payload,
                    timeout=max(self.settings.scrape_timeout_seconds + 5, 15),
                )
            )
            call["status_code"] = response.status_code
            call["success"] = response.ok
            if not response.ok:
                call["error_message"] = response.text[:500]
                return None
        body: dict[str, Any] = response.json()
        results = body.get("results", [])
        for item in results:
            if item.get("url") == url:
                content = str(item.get("raw_content") or "").strip()
                if content:
                    return content[: self.settings.extraction_max_source_chars]
        if results:
            content = str(results[0].get("raw_content") or "").strip()
            if content:
                return content[: self.settings.extraction_max_source_chars]
        return None

    def _build_query(self, *, search_query: str | None, title: str | None) -> str:
        parts = [part for part in (search_query, title, self.settings.tavily_extract_query) if part]
        return ". ".join(parts)
