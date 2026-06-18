from urllib.parse import urlparse

from app.config import Settings, get_settings
from tools.extraction_llm import ExtractionLLM, coerce_extraction_llm
from tools.groq_tool import GroqClient
from tools.model_routing import ModelTask
from tools.prompt_budget import slim_opportunity
from tools.prompt_loader import render_prompt


class SourceVerificationAgent:
    def __init__(
        self,
        settings: Settings | None = None,
        client: GroqClient | ExtractionLLM | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.llm = coerce_extraction_llm(client, self.settings)

    def verify(self, opportunity: dict, candidate: dict) -> dict:
        url = candidate.get("source_url") or opportunity.get("application_url") or ""
        domain = urlparse(str(url)).netloc.lower()
        tier = candidate.get("source_tier", "C")
        system = "You are a source trust and source verification agent. Return JSON only."
        user = render_prompt(
            "source_verification_prompt.txt",
            url=url,
            opportunity=slim_opportunity(opportunity),
        )
        payload = self.llm.json_chat(
            task=ModelTask.VERIFICATION,
            system=system,
            user=user,
            temperature=0.0,
        )
        trust = payload.get("trust_level")
        if trust not in {"trusted", "needs_review", "suspicious"}:
            raise ValueError("Source verification returned invalid trust_level.")
        notes = self._as_list(payload.get("notes"))
        reason = payload.get("reason")
        if reason:
            notes.insert(0, str(reason))
        risk_flags = self._as_list(payload.get("risk_flags"))
        risk_flags.extend(self._as_list(payload.get("warnings")))
        return {
            "trust_level": trust,
            "source_tier": str(payload.get("source_tier") or tier),
            "domain": str(payload.get("domain") or domain),
            "notes": notes,
            "risk_flags": risk_flags,
        }

    @staticmethod
    def _as_list(value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item not in (None, "")]
        return [str(value)]
