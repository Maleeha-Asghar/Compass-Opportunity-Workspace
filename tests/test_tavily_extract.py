from unittest.mock import MagicMock

from app.config import Settings
from tools.scraper_tool import WebScraper
from tools.web_search_tool import TavilyExtractClient


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.ok = status_code == 200
        self.text = str(payload)

    def json(self) -> dict:
        return self._payload


def test_tavily_extract_builds_focused_query() -> None:
    settings = Settings(
        TAVILY_EXTRACT_QUERY="application deadline eligibility requirements",
        TAVILY_EXTRACT_CHUNKS_PER_SOURCE=3,
    )
    client = TavilyExtractClient("tvly-test", settings=settings)

    query = client._build_query(
        search_query="data science scholarships Europe 2026",
        title="DAAD Scholarship",
    )

    assert "data science scholarships Europe 2026" in query
    assert "DAAD Scholarship" in query
    assert "application deadline eligibility requirements" in query


def test_tavily_extract_returns_focused_chunks(monkeypatch) -> None:
    settings = Settings(
        TAVILY_API_KEY="tvly-test",
        TAVILY_EXTRACT_ENABLED=True,
        EXTRACTION_MAX_SOURCE_CHARS=3500,
    )
    client = TavilyExtractClient("tvly-test", settings=settings)
    monkeypatch.setattr(
        "tools.web_search_tool.with_backoff",
        lambda fn: fn(),
    )
    monkeypatch.setattr(
        "tools.web_search_tool.requests.post",
        lambda *args, **kwargs: FakeResponse(
            {
                "results": [
                    {
                        "url": "https://www.daad.de/scholarships",
                        "raw_content": "Deadline: 2027-08-15 [...] Fully funded scholarship for international students.",
                    }
                ]
            }
        ),
    )

    content = client.extract_url(
        "https://www.daad.de/scholarships",
        search_query="DAAD scholarship",
        title="DAAD Scholarship",
    )

    assert content is not None
    assert "Deadline: 2027-08-15" in content


def test_web_scraper_prefers_tavily_extract(monkeypatch) -> None:
    settings = Settings(TAVILY_API_KEY="tvly-test", TAVILY_EXTRACT_ENABLED=True, RELATED_PAGE_SCRAPING_ENABLED=False)

    class FakeExtractor:
        def extract_url(self, url: str, *, search_query: str | None = None, title: str | None = None) -> str | None:
            assert search_query == "scholarships Europe"
            assert title == "DAAD Scholarship"
            return "Application deadline 2027-08-15. Fully funded for international students."

    class FakeRepository:
        def get_cached_source_page(self, url: str):
            return None

        def save_source_page(self, page, ttl_hours: int):
            return page

    class AllowPolicyGate:
        def check(self, url: str):
            return MagicMock(allowed=True, tier=MagicMock(value="B"), reason="allowed", domain="www.daad.de")

    scraper = WebScraper(
        settings=settings,
        policy_gate=AllowPolicyGate(),
        repository=FakeRepository(),
        tavily_extractor=FakeExtractor(),
    )

    page = scraper.scrape_page(
        "https://www.daad.de/scholarships",
        search_query="scholarships Europe",
        title="DAAD Scholarship",
    )

    assert page["content_type"] == "tavily_extract"
    assert "Application deadline 2027-08-15" in page["text"]


def test_web_scraper_adds_high_signal_related_pages(monkeypatch) -> None:
    settings = Settings(
        TAVILY_EXTRACT_ENABLED=False,
        MIN_DOMAIN_DELAY_SECONDS=0,
        MAX_RELATED_PAGES_PER_SOURCE=2,
        MAX_SCRAPE_CHARS=10_000,
    )

    pages = {
        "https://www.upf.edu/web/emai/access-admission": """
            <html><body><main>
              <h1>EMAI access and admission</h1>
              <p>Applicants need programming and computing science ECTS.</p>
              <a href="/web/emai/calendar">Application calendar</a>
              <a href="/web/emai/fees-scholarships">Fees and scholarships</a>
              <a href="/web/emai/student-life">Student life</a>
            </main></body></html>
        """,
        "https://www.upf.edu/web/emai/calendar": """
            <html><body><main>
              <h1>Calendar</h1>
              <p>Application deadline: 2027-01-12.</p>
            </main></body></html>
        """,
        "https://www.upf.edu/web/emai/fees-scholarships": """
            <html><body><main>
              <h1>Fees and scholarships</h1>
              <p>Erasmus Mundus scholarships cover tuition and include a monthly allowance.</p>
            </main></body></html>
        """,
    }

    class FakeHttpResponse:
        def __init__(self, text: str) -> None:
            self.text = text
            self.status_code = 200

        def raise_for_status(self) -> None:
            return None

    class FakeRepository:
        def __init__(self) -> None:
            self.cached: dict[str, dict] = {}

        def get_cached_source_page(self, url: str):
            return self.cached.get(url)

        def save_source_page(self, page, ttl_hours: int):
            self.cached[page["url"]] = page
            return page

    class AllowPolicyGate:
        def check(self, url: str):
            return MagicMock(allowed=True, tier=MagicMock(value="A"), reason="official university site", domain="www.upf.edu")

    def fake_get(url: str, **kwargs):
        return FakeHttpResponse(pages[url])

    monkeypatch.setattr("tools.scraper_tool.requests.get", fake_get)

    scraper = WebScraper(
        settings=settings,
        policy_gate=AllowPolicyGate(),
        repository=FakeRepository(),
    )

    page = scraper.scrape_page("https://www.upf.edu/web/emai/access-admission")

    assert page["content_type"] == "trafilatura_with_related" or page["content_type"] == "html_with_related"
    assert "Application deadline: 2027-01-12" in page["text"]
    assert "monthly allowance" in page["text"]
    assert set(page["related_urls"]) == {
        "https://www.upf.edu/web/emai/fees-scholarships",
        "https://www.upf.edu/web/emai/calendar",
    }


def test_web_scraper_ignores_failed_related_pages(monkeypatch) -> None:
    settings = Settings(
        TAVILY_EXTRACT_ENABLED=False,
        MIN_DOMAIN_DELAY_SECONDS=0,
        MAX_RELATED_PAGES_PER_SOURCE=1,
    )

    class FakeHttpResponse:
        def __init__(self, text: str, status_code: int = 200) -> None:
            self.text = text
            self.status_code = status_code

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError("failed")

    class FakeRepository:
        def get_cached_source_page(self, url: str):
            return None

        def save_source_page(self, page, ttl_hours: int):
            return page

    class AllowPolicyGate:
        def check(self, url: str):
            return MagicMock(allowed=True, tier=MagicMock(value="A"), reason="official university site", domain="www.upf.edu")

    def fake_get(url: str, **kwargs):
        if url.endswith("/calendar"):
            return FakeHttpResponse("server error", status_code=500)
        return FakeHttpResponse(
            """
            <html><body><main>
              <h1>EMAI access and admission</h1>
              <p>Applicants need programming and computing science ECTS.</p>
              <a href="/web/emai/calendar">Application calendar</a>
            </main></body></html>
            """
        )

    monkeypatch.setattr("tools.scraper_tool.requests.get", fake_get)

    scraper = WebScraper(
        settings=settings,
        policy_gate=AllowPolicyGate(),
        repository=FakeRepository(),
    )

    page = scraper.scrape_page("https://www.upf.edu/web/emai/access-admission")

    assert "Applicants need programming" in page["text"]
    assert "with_related" not in page["content_type"]
