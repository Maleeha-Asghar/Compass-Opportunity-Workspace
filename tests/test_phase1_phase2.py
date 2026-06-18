from datetime import date

from agents.profile_agent import ProfileAgent
from agents.search_planner_agent import SearchPlannerAgent
from app.graph import CompassGraph
from schemas.opportunity_schema import SearchResult
from schemas.profile_schema import StudentProfile


class FakeMistralClient:
    def json_chat(self, *, model, system, user, temperature=0.0, reasoning_effort=None, **kwargs):
        if "student profile facts" in system:
            return {
                "full_name": None,
                "country": "Pakistan",
                "degree": "BS Data Science",
                "field": "Data Science",
                "semester": "Final year",
                "cgpa": 3.8,
                "skills": [],
                "preferred_countries": [],
                "preferred_regions": ["Europe"],
                "preferred_opportunity_types": ["Scholarship"],
                "budget_preference": "Fully funded only",
                "ielts_status": "Not taken",
                "gre_status": None,
                "career_goal": None,
            }
        if "web search queries" in system:
            return {
                "queries": [
                    "fully funded Data Science scholarships Europe Pakistan students 2026 2027",
                    "Erasmus Mundus Data Science scholarship 2026 Pakistan students",
                    "DAAD Data Science masters scholarship Pakistan 2026 application",
                    "fully funded AI scholarships Europe Pakistani students 2027",
                    "Data Science research internship Europe 2026 2027",
                ]
            }
        if "structured opportunity data" in system:
            return {
                "title": "Fully funded Data Science Scholarship 2027",
                "provider": "DAAD",
                "country": "Germany",
                "opportunity_type": "Scholarship",
                "deadline": "2027-08-15",
                "funding_type": "Fully funded",
                "eligibility": ["International Data Science students"],
                "required_documents": ["CV"],
                "application_url": "https://www.daad.de/en/studying-in-germany/scholarships/",
                "contact_email": None,
                "summary": "Fully funded Data Science scholarship for international students in Germany.",
                "payment_requested": False,
                "warnings": [],
                "extraction_notes": [],
            }
        if "source trust" in system:
            return {"trust_level": "trusted", "source_tier": "B", "domain": "www.daad.de", "notes": ["official"], "risk_flags": []}
        if "whether a student is eligible" in system:
            return {"eligible": True, "score": 0.85, "reasons": ["fit"], "missing_requirements": [], "deadline_passed": False}
        if "Rank opportunities" in system:
            return {"ranked": [{"index": 0, "priority_score": 0.92, "priority": "high", "ranking_reason": "Strong fit"}]}
        return {}


def test_profile_agent_extracts_core_profile_fields() -> None:
    text = (
        "I am a final year BS Data Science student from Pakistan with 3.8 CGPA. "
        "I want fully funded AI scholarships in Europe. I have not taken IELTS yet."
    )

    profile = ProfileAgent(client=FakeMistralClient()).update_profile(None, text)

    assert profile.country == "Pakistan"
    assert profile.degree == "BS Data Science"
    assert profile.field == "Data Science"
    assert profile.cgpa == 3.8
    assert profile.budget_preference == "Fully funded only"
    assert profile.ielts_status == "Not taken"
    assert "Europe" in profile.preferred_regions


def test_search_planner_coerces_object_queries() -> None:
    class DictQueryPlannerClient(FakeMistralClient):
        def json_chat(self, *, model, system, user, temperature=0.0, reasoning_effort=None, **kwargs):
            if "web search queries" in system:
                return {
                    "queries": [
                        {"query": "fully funded data science scholarships Europe 2026 2027", "description": "general"},
                        {"query": "Erasmus Mundus data science scholarship 2026 Pakistan", "description": "official"},
                        {"query": "DAAD data science masters scholarship Pakistan 2026", "description": "official"},
                        {"query": "fully funded AI scholarships Europe Pakistani students 2027", "description": "general"},
                        {"query": "data science research internship Europe 2026 2027", "description": "general"},
                    ]
                }
            return super().json_chat(
                model=model,
                system=system,
                user=user,
                temperature=temperature,
                reasoning_effort=reasoning_effort,
            )

    profile = StudentProfile(field="Data Science", preferred_regions=["Europe"])
    queries = SearchPlannerAgent(client=DictQueryPlannerClient()).plan(profile.model_dump(), today=date(2026, 6, 12))

    assert len(queries) == 5
    assert all("{" not in query for query in queries)
    assert queries[0].startswith("fully funded data science scholarships Europe")


def test_search_planner_uses_current_and_next_year() -> None:
    profile = StudentProfile(
        country="Pakistan",
        field="Data Science",
        preferred_regions=["Europe"],
        budget_preference="Fully funded only",
        preferred_opportunity_types=["Scholarship"],
    )

    queries = SearchPlannerAgent(client=FakeMistralClient()).plan(profile.model_dump(), today=date(2026, 6, 12))

    assert len(queries) == 5
    assert any("2026" in query and "2027" in query for query in queries)
    assert any("fully funded" in query.lower() for query in queries)
    assert any("daad" in query.lower() or "erasmus" in query.lower() for query in queries)


class FakeSearchProvider:
    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        return [
            SearchResult(
                title="Fully funded Data Science Scholarship 2027",
                url="https://www.daad.de/en/studying-in-germany/scholarships/",
                snippet="Fully funded scholarship for Data Science students. Deadline 2027-08-15.",
                source="test",
            )
        ]


class FailingSearchProvider:
    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        raise RuntimeError("search provider unavailable")


class FakeScraper:
    def scrape_page(self, url: str, *, search_query: str | None = None, title: str | None = None) -> dict:
        return {
            "url": url,
            "content_type": "html",
            "text": "Fully funded Data Science scholarship for international students in Germany. Deadline 2027-08-15.",
            "tier": "B",
            "reason": "test fixture",
        }


class FailingPlannerClient(FakeMistralClient):
    def json_chat(self, *, model, system, user, temperature=0.0, reasoning_effort=None, **kwargs):
        if "web search queries" in system:
            raise RuntimeError("Groq planning unavailable")
        return super().json_chat(
            model=model,
            system=system,
            user=user,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
        )


class FakeRepository:
    def __init__(self) -> None:
        self.saved = []
        self.saved_profiles = []
        self.job_updates = []
        self.jobs: dict[str, dict] = {}

    def save_opportunity(self, opportunity: dict, sources: list[dict]) -> dict:
        record = {**opportunity, "id": f"{len(self.saved) + 1:03d}"}
        self.saved.append((record, sources))
        return record

    def save_profile(self, user_id: str, profile: dict) -> dict:
        record = {"id": "profile-1", "user_id": user_id, **profile}
        self.saved_profiles.append(record)
        return record

    def match_opportunities(self, embedding: list[float], threshold: float = 0.88, limit: int = 5) -> list[dict]:
        return []

    def save_opportunity_embedding(self, opportunity_id: str, embedding: list[float]) -> dict:
        return {"opportunity_id": opportunity_id, "embedding": embedding}

    def update_search_job(self, job_id: str, **updates):
        self.job_updates.append((job_id, updates))
        current = self.jobs.get(job_id, {"id": job_id})
        current.update(updates)
        self.jobs[job_id] = current
        return current

    def get_search_job_by_id(self, job_id: str) -> dict | None:
        return self.jobs.get(job_id)

    def fail_search_job(self, job_id: str, error: str, progress_message: str = "Search failed") -> dict:
        return self.update_search_job(
            job_id,
            status="failed",
            progress_message=progress_message,
            error=error,
            completed_at="2026-06-12T00:00:00+00:00",
        )


class FakeEmbeddingTool:
    def embed_opportunity(self, opportunity: dict) -> list[float]:
        return [0.1] * 1024


def test_graph_search_flow_returns_ranked_opportunities() -> None:
    graph = CompassGraph(
        search_provider=FakeSearchProvider(),
        scraper=FakeScraper(),
        repository=FakeRepository(),
        embedding_tool=FakeEmbeddingTool(),
        llm_client=FakeMistralClient(),
    )

    result = graph.invoke(
        {
            "user_query": "Find fully funded Data Science scholarships in Europe for Pakistani students",
            "today": "2026-06-12",
            "errors": [],
        }
    )

    assert result["intent"] == "find_opportunities"
    assert result["search_queries"]
    assert result["raw_search_results"]
    assert result["candidates"]
    assert result["prioritized_opportunities"]
    assert all(item["source_tier"] == "B" for item in result["prioritized_opportunities"])
    assert result["prioritized_opportunities"][0]["priority"] in {"high", "medium", "low"}


def test_profile_update_only_saves_without_search_planning() -> None:
    repository = FakeRepository()
    graph = CompassGraph(
        search_provider=FakeSearchProvider(),
        scraper=FakeScraper(),
        repository=repository,
        embedding_tool=FakeEmbeddingTool(),
        llm_client=FakeMistralClient(),
    )

    result = graph.update_profile_only(
        user_id="user-1",
        text="I am a final year BS Data Science student from Pakistan with 3.8 CGPA.",
    )

    assert result["profile"]["country"] == "Pakistan"
    assert result["saved_profile"]["user_id"] == "user-1"
    assert repository.saved_profiles
    assert "search_queries" not in result


def test_search_flow_reports_provider_errors_without_crashing() -> None:
    graph = CompassGraph(
        search_provider=FailingSearchProvider(),
        scraper=FakeScraper(),
        repository=FakeRepository(),
        embedding_tool=FakeEmbeddingTool(),
        llm_client=FakeMistralClient(),
    )

    result = graph.invoke(
        {
            "user_query": "Find fully funded AI scholarships in Europe for Pakistani students",
            "today": "2026-06-12",
            "errors": [],
        }
    )

    assert result["prioritized_opportunities"] == []
    assert result["errors"]
    assert "search provider unavailable" in result["errors"][0]


def test_search_run_emits_stage_updates() -> None:
    repository = FakeRepository()
    graph = CompassGraph(
        search_provider=FakeSearchProvider(),
        scraper=FakeScraper(),
        repository=repository,
        embedding_tool=FakeEmbeddingTool(),
        llm_client=FakeMistralClient(),
    )

    graph.run_search_job(
        job_id="job-1",
        user_id="user-1",
        query="Find fully funded AI scholarships in Europe for Pakistani students",
        profile={"_max_results_per_query": 2},
    )

    messages = [updates["progress_message"] for _, updates in repository.job_updates if "progress_message" in updates]
    assert any(message.startswith("Planning search queries") for message in messages)
    assert any("Searching trusted sources" in message for message in messages)
    assert any("Scraping source pages" in message for message in messages)
    assert any("Extracting opportunity details" in message for message in messages)
    assert any("Verifying source trust" in message for message in messages)
    assert any("Deduplicated" in message for message in messages)
    assert any("Saving" in message for message in messages)
    assert repository.jobs["job-1"]["status"] == "completed"


def test_search_job_planning_failure_stays_failed() -> None:
    repository = FakeRepository()
    graph = CompassGraph(
        search_provider=FakeSearchProvider(),
        scraper=FakeScraper(),
        repository=repository,
        embedding_tool=FakeEmbeddingTool(),
        llm_client=FailingPlannerClient(),
    )

    graph.run_search_job(
        job_id="job-planning-fail",
        user_id="user-1",
        query="Find scholarships",
        profile={"_max_results_per_query": 2},
    )

    job = repository.jobs["job-planning-fail"]
    assert job["status"] == "failed"
    assert "Search planning failed" in job["progress_message"]
    assert "Groq planning unavailable" in job["error"]
