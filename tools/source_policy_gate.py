import time
import urllib.robotparser as robotparser
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

from app.config import Settings, get_settings
from schemas.opportunity_schema import SourceTier


ALLOWLIST_DOMAINS = {
    "daad.de",
    "www.daad.de",
    "eacea.ec.europa.eu",
    "chevening.org",
    "www.chevening.org",
    "fulbrightonline.org",
    "cscuk.fcdo.gov.uk",
}

DENYLIST_DOMAINS = {
    "reddit.com",
    "www.reddit.com",
    "old.reddit.com",
    "quora.com",
    "www.quora.com",
    "medium.com",
    "www.medium.com",
    "facebook.com",
    "www.facebook.com",
    "twitter.com",
    "www.twitter.com",
    "x.com",
    "www.x.com",
    "tiktok.com",
    "www.tiktok.com",
    "pinterest.com",
    "www.pinterest.com",
    "expresstechjobs.com",
    "www.expresstechjobs.com",
    "expatrio.com",
    "www.expatrio.com",
}

AGGREGATOR_DOMAINS = {
    "scholarshipsads.com",
    "www.scholarshipsads.com",
    "expresstechjobs.com",
    "www.expresstechjobs.com",
    "expatrio.com",
    "www.expatrio.com",
}

OFFICIAL_DOMAIN_HINTS = (".edu", ".ac.uk", ".ac.", ".gov", ".gouv", "europa.eu")


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    tier: SourceTier
    reason: str
    domain: str


class SourcePolicyGate:
    def __init__(self, user_agent: str = "CompassBot", settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.user_agent = user_agent
        self._robots_cache: dict[str, tuple[robotparser.RobotFileParser | None, float]] = {}
        self.cache_ttl_seconds = 24 * 60 * 60

    @staticmethod
    def normalize_domain(domain: str) -> str:
        return domain.lower().removeprefix("www.")

    @classmethod
    def is_denied_search_domain(cls, domain: str) -> bool:
        normalized = cls.normalize_domain(domain)
        if normalized in {cls.normalize_domain(item) for item in DENYLIST_DOMAINS}:
            return True
        return any(normalized == cls.normalize_domain(item) or normalized.endswith(f".{cls.normalize_domain(item)}") for item in DENYLIST_DOMAINS)

    @classmethod
    def is_official_edu_domain(cls, domain: str) -> bool:
        normalized = domain.lower()
        if cls.normalize_domain(normalized) in {cls.normalize_domain(item) for item in ALLOWLIST_DOMAINS}:
            return True
        return any(hint in normalized for hint in OFFICIAL_DOMAIN_HINTS)

    @classmethod
    def is_aggregator_domain(cls, domain: str) -> bool:
        normalized = cls.normalize_domain(domain)
        return normalized in {cls.normalize_domain(item) for item in AGGREGATOR_DOMAINS}

    @classmethod
    def search_result_score(cls, url: str) -> int | None:
        domain = urlparse(url).netloc.lower()
        if not domain or cls.is_denied_search_domain(domain):
            return None
        if cls.is_official_edu_domain(domain):
            return 100
        if cls.is_aggregator_domain(domain):
            return 15
        return 50

    @classmethod
    def rank_search_results(cls, results: list[dict], *, min_results: int = 5) -> list[dict]:
        scored: list[tuple[int, dict]] = []
        for result in results:
            score = cls.search_result_score(str(result.get("url") or ""))
            if score is None:
                continue
            scored.append((score, result))
        scored.sort(key=lambda item: item[0], reverse=True)
        official = [result for score, result in scored if score >= 80]
        fallback = [result for score, result in scored if score < 80]
        if len(official) >= min_results:
            return official
        combined = official + fallback
        return combined[: max(min_results * 2, len(combined))]

    def check(self, url: str) -> PolicyDecision:
        domain = urlparse(url).netloc.lower()
        if not domain:
            return PolicyDecision(False, SourceTier.C, "invalid URL", domain="")
        if domain in DENYLIST_DOMAINS:
            return PolicyDecision(False, SourceTier.D, "denylisted domain", domain=domain)

        parser = self._get_robots_parser(domain)
        if parser is None:
            tier = SourceTier.B if domain in ALLOWLIST_DOMAINS else SourceTier.C
            return PolicyDecision(False, tier, "robots.txt unreadable, defaulting to link-only", domain)

        allowed = parser.can_fetch(self.user_agent, url)
        tier = SourceTier.B if domain in ALLOWLIST_DOMAINS else SourceTier.A
        if not allowed:
            tier = SourceTier.C
        return PolicyDecision(allowed, tier, "robots.txt check", domain)

    def _get_robots_parser(self, domain: str) -> robotparser.RobotFileParser | None:
        cached = self._robots_cache.get(domain)
        now = time.time()
        if cached and now - cached[1] < self.cache_ttl_seconds:
            return cached[0]

        parser = robotparser.RobotFileParser()
        robots_url = f"https://{domain}/robots.txt"
        parser.set_url(robots_url)
        try:
            response = requests.get(robots_url, timeout=self.settings.robots_timeout_seconds, headers={"User-Agent": self.user_agent})
            response.raise_for_status()
            parser.parse(response.text.splitlines())
        except requests.RequestException:
            self._robots_cache[domain] = (None, now)
            return None

        self._robots_cache[domain] = (parser, now)
        return parser
