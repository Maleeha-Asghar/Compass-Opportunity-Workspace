import time
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.config import Settings, get_settings
from tools.content_extractor import clean_html_to_text
from tools.source_policy_gate import SourcePolicyGate
from tools.supabase_tool import SupabaseRepository


class WebScraper:
    RELATED_PAGE_KEYWORDS = (
        "admission",
        "apply",
        "application",
        "calendar",
        "deadline",
        "dates",
        "eligibility",
        "fees",
        "funding",
        "how to apply",
        "requirements",
        "scholarship",
        "tuition",
        "documents",
    )
    SKIPPED_RELATED_EXTENSIONS = (
        ".avi",
        ".css",
        ".doc",
        ".docx",
        ".gif",
        ".jpg",
        ".jpeg",
        ".js",
        ".mp4",
        ".pdf",
        ".png",
        ".ppt",
        ".pptx",
        ".svg",
        ".webp",
        ".xls",
        ".xlsx",
        ".zip",
    )

    def __init__(
        self,
        settings: Settings | None = None,
        policy_gate: SourcePolicyGate | None = None,
        repository: SupabaseRepository | None = None,
        tavily_extractor: Any | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.policy_gate = policy_gate or SourcePolicyGate(self.settings.http_user_agent, self.settings)
        self.repository = repository or SupabaseRepository(self.settings)
        self._last_request_time: dict[str, float] = {}
        self._tavily_extractor = tavily_extractor
        if self._tavily_extractor is None and self.settings.tavily_extract_enabled and self.settings.tavily_api_key:
            from tools.web_search_tool import TavilyExtractClient

            self._tavily_extractor = TavilyExtractClient(self.settings.tavily_api_key, settings=self.settings)

    def scrape_page(self, url: str, *, search_query: str | None = None, title: str | None = None) -> dict:
        cached = self.repository.get_cached_source_page(url)
        if cached:
            has_related_context = cached.get("related_urls") or str(cached.get("content_type") or "").endswith("_with_related")
            if self.settings.related_page_scraping_enabled and not has_related_context:
                cached = None
            else:
                return {
                    "url": cached["url"],
                    "content_type": cached["content_type"],
                    "text": cached.get("text") or "",
                    "table_data": cached.get("table_data") or "",
                    "tier": cached["source_tier"],
                    "reason": "source_pages cache hit",
                }
        policy = self.policy_gate.check(url)
        if not policy.allowed:
            page = {
                "url": url,
                "content_type": "link_only",
                "text": "",
                "tier": policy.tier.value,
                "reason": policy.reason,
            }
            self.repository.save_source_page(page, ttl_hours=24)
            return page

        if self._tavily_extractor and self.settings.tavily_extract_enabled:
            extracted = self._tavily_extractor.extract_url(url, search_query=search_query, title=title)
            if extracted:
                page = {
                    "url": url,
                    "content_type": "tavily_extract",
                    "text": extracted[: self.settings.max_scrape_chars],
                    "table_data": "",
                    "tier": policy.tier.value,
                    "reason": "tavily extract focused chunks",
                    "domain": policy.domain,
                }
                if self.settings.related_page_scraping_enabled:
                    page = self._safe_augment_extracted_page_with_related_links(
                        page,
                        base_url=url,
                        tier=policy.tier.value,
                        domain=policy.domain,
                    )
                return self._cache_and_return(page, self.settings.source_cache_ttl_hours)

        if self.settings.scrape_playwright_first and self.settings.dynamic_scraping_enabled:
            dynamic = self.scrape_dynamic_page(url, policy.tier.value)
            if dynamic.get("text"):
                return self._cache_and_return(dynamic, self.settings.source_cache_ttl_hours)

        self._respect_rate_limit(policy.domain)
        try:
            response = requests.get(
                url,
                timeout=self.settings.scrape_timeout_seconds,
                headers={"User-Agent": self.settings.http_user_agent},
            )
        except requests.RequestException as exc:
            return self._cache_and_return(self._link_only(url, "C", f"request failed: {exc.__class__.__name__}"), 24)

        if response.status_code in (403, 429, 503):
            return self._cache_and_return(
                self._link_only(url, "C", f"status {response.status_code}, storing link-only source"),
                24,
            )
        response.raise_for_status()
        page = self._page_from_html(
            url=url,
            html=response.text,
            tier=policy.tier.value,
            reason=policy.reason,
            domain=policy.domain,
            content_type="html",
        )
        if self.settings.related_page_scraping_enabled:
            page = self._safe_augment_with_related_pages(
                page,
                base_url=url,
                html=response.text,
                tier=policy.tier.value,
                domain=policy.domain,
            )
        if self.settings.dynamic_scraping_enabled and len(page["text"]) < 500:
            dynamic = self.scrape_dynamic_page(url, policy.tier.value)
            if dynamic.get("text"):
                return self._cache_and_return(dynamic, self.settings.source_cache_ttl_hours)
        return self._cache_and_return(page, self.settings.source_cache_ttl_hours)

    def _fetch_html(self, url: str, domain: str) -> str | None:
        self._respect_rate_limit(domain)
        try:
            response = requests.get(
                url,
                timeout=self.settings.scrape_timeout_seconds,
                headers={"User-Agent": self.settings.http_user_agent},
            )
        except requests.RequestException:
            return None
        if response.status_code in (403, 429, 503):
            return None
        try:
            response.raise_for_status()
        except requests.RequestException:
            return None
        return response.text

    def _safe_augment_extracted_page_with_related_links(
        self,
        page: dict,
        *,
        base_url: str,
        tier: str,
        domain: str | None,
    ) -> dict:
        try:
            return self._augment_extracted_page_with_related_links(
                page,
                base_url=base_url,
                tier=tier,
                domain=domain,
            )
        except Exception as exc:
            return {
                **page,
                "reason": f"{page.get('reason')}; related page scrape skipped: {exc.__class__.__name__}",
            }

    def _augment_extracted_page_with_related_links(
        self,
        page: dict,
        *,
        base_url: str,
        tier: str,
        domain: str | None,
    ) -> dict:
        policy_domain = domain or urlparse(base_url).netloc
        html = self._fetch_html(base_url, policy_domain)
        if not html:
            return page
        return self._augment_with_related_pages(
            page,
            base_url=base_url,
            html=html,
            tier=tier,
            domain=domain,
        )

    def _safe_augment_with_related_pages(
        self,
        page: dict,
        *,
        base_url: str,
        html: str,
        tier: str,
        domain: str | None,
    ) -> dict:
        try:
            return self._augment_with_related_pages(
                page,
                base_url=base_url,
                html=html,
                tier=tier,
                domain=domain,
            )
        except Exception as exc:
            return {
                **page,
                "reason": f"{page.get('reason')}; related page scrape skipped: {exc.__class__.__name__}",
            }

    def scrape_dynamic_page(self, url: str, tier: str | None = None) -> dict:
        policy = self.policy_gate.check(url)
        if not policy.allowed:
            return self._link_only(url, policy.tier.value, policy.reason)
        self._respect_rate_limit(policy.domain)
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("playwright is required for dynamic scraping.") from exc

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(user_agent=self.settings.http_user_agent)
            page.goto(url, wait_until="networkidle", timeout=30000)
            html = page.content()
            browser.close()
        return self._page_from_html(
            url=url,
            html=html,
            tier=tier or policy.tier.value,
            reason="dynamic page scrape",
            domain=policy.domain,
            content_type="dynamic_html",
        )

    def _respect_rate_limit(self, domain: str) -> None:
        last = self._last_request_time.get(domain, 0)
        wait = self.settings.min_domain_delay_seconds - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        self._last_request_time[domain] = time.time()

    def _page_from_html(
        self,
        *,
        url: str,
        html: str,
        tier: str,
        reason: str,
        domain: str | None,
        content_type: str,
    ) -> dict:
        if self.settings.scrape_use_trafilatura:
            cleaned = clean_html_to_text(html, url=url)
            text = cleaned["text"]
            table_data = cleaned["table_data"]
            resolved_type = cleaned["content_type"] if content_type == "html" else content_type
        else:
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "noscript"]):
                tag.decompose()
            text = " ".join(soup.get_text(separator=" ").split())
            table_data = ""
            resolved_type = content_type
        return {
            "url": url,
            "content_type": resolved_type,
            "text": text[: self.settings.max_scrape_chars],
            "table_data": table_data[: self.settings.max_scrape_chars],
            "tier": tier,
            "reason": reason,
            "domain": domain or urlparse(url).netloc,
        }

    def _augment_with_related_pages(
        self,
        page: dict,
        *,
        base_url: str,
        html: str,
        tier: str,
        domain: str | None,
    ) -> dict:
        limit = max(0, int(self.settings.max_related_pages_per_source))
        if limit == 0:
            return page
        related_blocks: list[str] = []
        related_tables: list[str] = []
        related_urls: list[str] = []
        for related_url in self._related_link_candidates(base_url, html)[:limit]:
            cached = self.repository.get_cached_source_page(related_url)
            if cached:
                related_page = {
                    "url": cached["url"],
                    "content_type": cached["content_type"],
                    "text": cached.get("text") or "",
                    "table_data": cached.get("table_data") or "",
                }
            else:
                related_page = self._fetch_related_page(related_url, tier=tier, domain=domain)
            text = str(related_page.get("text") or "").strip()
            table_data = str(related_page.get("table_data") or "").strip()
            if not text and not table_data:
                continue
            related_urls.append(related_url)
            if text:
                related_blocks.append(f"Related page: {related_url}\n{text}")
            if table_data:
                related_tables.append(f"Related page: {related_url}\n{table_data}")
        if not related_blocks and not related_tables:
            return page
        merged_text = "\n\n".join([str(page.get("text") or ""), *related_blocks]).strip()
        merged_tables = "\n\n".join([str(page.get("table_data") or ""), *related_tables]).strip()
        notes = f"{page.get('reason')}; related pages scraped: {', '.join(related_urls)}"
        return {
            **page,
            "text": merged_text[: self.settings.max_scrape_chars],
            "table_data": merged_tables[: self.settings.max_scrape_chars],
            "content_type": f"{page.get('content_type')}_with_related",
            "reason": notes,
            "related_urls": related_urls,
        }

    def _fetch_related_page(self, url: str, *, tier: str, domain: str | None) -> dict:
        policy = self.policy_gate.check(url)
        if not policy.allowed:
            return self._link_only(url, policy.tier.value, policy.reason)
        self._respect_rate_limit(policy.domain)
        try:
            response = requests.get(
                url,
                timeout=self.settings.scrape_timeout_seconds,
                headers={"User-Agent": self.settings.http_user_agent},
            )
        except requests.RequestException as exc:
            return self._link_only(url, "C", f"related page request failed: {exc.__class__.__name__}")
        if response.status_code in (403, 429, 503):
            return self._link_only(url, "C", f"related page status {response.status_code}")
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            return self._link_only(url, "C", f"related page request failed: {exc.__class__.__name__}")
        related_page = self._page_from_html(
            url=url,
            html=response.text,
            tier=tier,
            reason="related page scrape",
            domain=domain or policy.domain,
            content_type="html",
        )
        return self._cache_and_return(related_page, self.settings.source_cache_ttl_hours)

    def _related_link_candidates(self, base_url: str, html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        scored: dict[str, int] = {}
        for anchor in soup.find_all("a", href=True):
            href = str(anchor.get("href") or "").strip()
            absolute_url = self._normalized_related_url(base_url, href)
            if not absolute_url or absolute_url == self._normalized_related_url(base_url, base_url):
                continue
            if not self._same_site_context(base_url, absolute_url):
                continue
            label = " ".join(anchor.get_text(" ", strip=True).split())
            haystack = f"{label} {absolute_url}".lower()
            score = sum(1 for keyword in self.RELATED_PAGE_KEYWORDS if keyword in haystack)
            if score == 0:
                continue
            scored[absolute_url] = max(scored.get(absolute_url, 0), score)
        return [
            url
            for url, _score in sorted(
                scored.items(),
                key=lambda item: (-item[1], len(urlparse(item[0]).path), item[0]),
            )
        ]

    def _normalized_related_url(self, base_url: str, href: str) -> str | None:
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            return None
        absolute_url, _fragment = urldefrag(urljoin(base_url, href))
        parsed = urlparse(absolute_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return None
        if parsed.path.lower().endswith(self.SKIPPED_RELATED_EXTENSIONS):
            return None
        return absolute_url

    @staticmethod
    def _same_site_context(base_url: str, candidate_url: str) -> bool:
        base = urlparse(base_url)
        candidate = urlparse(candidate_url)
        if base.netloc.lower() != candidate.netloc.lower():
            return False
        base_parts = [part for part in base.path.split("/") if part]
        candidate_parts = [part for part in candidate.path.split("/") if part]
        if not base_parts:
            return True
        shared_prefix = 0
        for base_part, candidate_part in zip(base_parts, candidate_parts):
            if base_part != candidate_part:
                break
            shared_prefix += 1
        return shared_prefix >= min(2, len(base_parts))

    @staticmethod
    def _link_only(url: str, tier: str, reason: str) -> dict:
        domain = urlparse(url).netloc
        return {
            "url": url,
            "content_type": "link_only",
            "text": "",
            "table_data": "",
            "tier": tier,
            "reason": reason,
            "domain": domain,
        }

    def _cache_and_return(self, page: dict, ttl_hours: int) -> dict:
        self.repository.save_source_page(page, ttl_hours=ttl_hours)
        return page
