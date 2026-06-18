from agents.extraction_agent import OpportunityExtractionAgent
from tools.model_routing import ModelTask


class FakeExtractionLLM:
    provider = "groq"
    model = "test-model"
    calls: list[tuple[str, str, object]] = []

    def json_chat(
        self,
        *,
        task=None,
        system: str,
        user: str,
        temperature: float = 0.0,
        model=None,
        timeout=None,
        max_retries=None,
    ):
        self.calls.append((system, user, task))
        if task == ModelTask.DEADLINE or "deadline extraction agent" in system.lower() or "deadline extraction agent" in user:
            return {
                "deadlines": [
                    {
                        "date": "2026-08-15",
                        "description": "Application deadline",
                        "type": "application_deadline",
                        "confidence": "high",
                    }
                ]
            }
        if task == ModelTask.TABLE or "tabular data" in user:
            return {"rows": []}
        return {
            "is_opportunity": True,
            "title": "DAAD Scholarship",
            "provider": "DAAD",
            "opportunity_type": "scholarship",
            "country": "Germany",
            "location": None,
            "funding_type": "Fully funded",
            "deadline": "2026-08-15",
            "deadline_text": "15 August 2026",
            "application_open_date": None,
            "program_start_date": None,
            "degree_level": ["Masters"],
            "field_of_study": ["Data Science"],
            "eligible_countries": ["International"],
            "eligibility_requirements": ["Bachelor degree"],
            "required_documents": ["CV"],
            "benefits": ["Tuition waiver"],
            "application_url": "https://www.daad.de/apply",
            "official_url": "https://www.daad.de/scholarship",
            "contact_email": "info@daad.de",
            "source_confidence": "high",
            "summary": "Fully funded scholarship in Germany.",
            "warnings": [],
        }


def test_opportunity_extraction_runs_multi_step_pipeline() -> None:
    llm = FakeExtractionLLM()
    agent = OpportunityExtractionAgent(client=llm)
    result = agent.extract(
        {
            "title": "DAAD Scholarship",
            "source_url": "https://www.daad.de/scholarship",
            "page_text": "Application deadline 2026-08-15 for international students.",
            "table_data": "",
            "content_type": "trafilatura",
        }
    )

    assert len(llm.calls) == 2
    assert llm.calls[0][2] == ModelTask.DEADLINE
    assert llm.calls[1][2] == ModelTask.OPPORTUNITY
    assert result["title"] == "DAAD Scholarship"
    assert result["deadline"] == "2026-08-15"
    assert result["eligibility"] == ["Bachelor degree"]
    assert "degree_level: Masters" in result["extraction_notes"]


def test_opportunity_extraction_rejects_non_opportunity_pages() -> None:
    class RejectLLM(FakeExtractionLLM):
        def json_chat(self, *, task=None, system: str, user: str, temperature: float = 0.0, model=None, timeout=None, max_retries=None):
            if task == ModelTask.DEADLINE or "deadline extraction agent" in user:
                return {"deadlines": []}
            if task == ModelTask.TABLE or "tabular data" in user:
                return {"rows": []}
            return {"is_opportunity": False, "title": "Blog post"}

    agent = OpportunityExtractionAgent(client=RejectLLM())
    try:
        agent.extract(
            {
                "title": "Blog post",
                "source_url": "https://example.com/blog",
                "page_text": "This is only a news article.",
                "table_data": "",
            }
        )
        raised = False
    except ValueError as exc:
        raised = True
        assert "does not describe an opportunity" in str(exc)
    assert raised
