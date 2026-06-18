from unittest.mock import MagicMock

from app.config import Settings
from agents.deadline_extraction_agent import DeadlineExtractionAgent
from tools.extraction_llm import ExtractionLLM
from tools.model_routing import ModelTask, has_date_signals


def test_has_date_signals_detects_deadline_keywords() -> None:
    assert has_date_signals("Application deadline is 15 August 2026.")
    assert not has_date_signals("This page explains our mission and values.")


def test_route_opportunity_to_mistral_when_configured() -> None:
    settings = Settings(
        MISTRAL_API_KEY="mistral-test",
        GROQ_API_KEY="groq-test",
        EXTRACTION_MODEL="mistral-large-latest",
        FAST_MODEL="llama-3.1-8b-instant",
    )
    router = ExtractionLLM(settings=settings)
    assert router.route(ModelTask.OPPORTUNITY) == ("mistral", "mistral-large-latest")
    assert router.route(ModelTask.DEADLINE) == ("groq", "llama-3.1-8b-instant")
    assert router.route(ModelTask.VERIFICATION) == ("groq", "llama-3.1-8b-instant")
    assert router.route(ModelTask.ELIGIBILITY) == ("groq", "llama-3.1-8b-instant")


def test_route_opportunity_to_groq_without_mistral_key() -> None:
    settings = Settings(GROQ_API_KEY="groq-test", MISTRAL_API_KEY=None)
    router = ExtractionLLM(settings=settings)
    assert router.route(ModelTask.OPPORTUNITY) == ("groq", "llama-3.1-8b-instant")


def test_json_chat_uses_groq_for_verification_even_with_mistral() -> None:
    settings = Settings(
        MISTRAL_API_KEY="mistral-test",
        GROQ_API_KEY="groq-test",
        EXTRACTION_MODEL="mistral-large-latest",
    )
    groq = MagicMock()
    groq.json_chat.return_value = {"trust_level": "trusted", "source_tier": "A", "domain": "example.edu"}
    router = ExtractionLLM(settings=settings, groq=groq)

    router.json_chat(
        task=ModelTask.VERIFICATION,
        system="verify",
        user="payload",
    )

    groq.json_chat.assert_called_once()
    assert groq.json_chat.call_args.kwargs["model"] == settings.fast_model


def test_deadline_agent_skips_llm_without_date_signals() -> None:
    class TrackingLLM:
        calls = 0

        def json_chat(self, **kwargs):
            self.calls += 1
            return {"deadlines": []}

    llm = TrackingLLM()
    agent = DeadlineExtractionAgent(
        settings=Settings(EXTRACTION_SKIP_DEADLINE_WITHOUT_DATES=True),
        llm=llm,
    )
    result = agent.extract("General information about studying abroad with no dates mentioned.")
    assert result == {"deadlines": []}
    assert llm.calls == 0
