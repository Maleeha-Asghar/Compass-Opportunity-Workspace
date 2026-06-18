from datetime import date
from typing import Any

from app.config import Settings, get_settings
from tools.extraction_llm import ExtractionLLM, coerce_extraction_llm
from tools.groq_tool import GroqClient
from tools.model_routing import ModelTask
from tools.prompt_budget import slim_opportunity, slim_profile
from tools.prompt_loader import render_prompt


class EligibilityAgent:
    def __init__(
        self,
        settings: Settings | None = None,
        client: GroqClient | ExtractionLLM | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.llm = coerce_extraction_llm(client, self.settings)

    def evaluate(self, profile: dict[str, Any], opportunity: dict[str, Any], today: date) -> dict[str, Any]:
        deadline_passed = self._deadline_passed(opportunity.get("deadline"), today)
        system = "You are an eligibility evaluation agent. Return JSON only."
        user = render_prompt(
            "eligibility_prompt.txt",
            today=today.isoformat(),
            deadline_passed=str(deadline_passed).lower(),
            profile=slim_profile(profile),
            opportunity=slim_opportunity(opportunity),
        )
        payload = self.llm.json_chat(
            task=ModelTask.ELIGIBILITY,
            system=system,
            user=user,
            temperature=0.0,
        )
        missing = self._as_list(payload.get("missing_requirements"))
        missing.extend(self._as_list(payload.get("unclear_requirements")))
        if deadline_passed and "Deadline has passed." not in missing:
            missing.append("Deadline has passed.")
        reasons = self._as_list(payload.get("reasons"))
        reasons.extend(self._as_list(payload.get("matched_requirements")))
        recommendation = payload.get("recommendation")
        if recommendation:
            reasons.append(str(recommendation))
        score = max(0.0, min(1.0, float(payload.get("score", 0))))
        status = str(payload.get("eligibility_status") or "").lower()
        eligible = bool(payload.get("eligible", status == "eligible"))
        return {
            "eligible": eligible and not deadline_passed,
            "score": score,
            "reasons": reasons,
            "missing_requirements": missing,
            "deadline_passed": deadline_passed,
        }

    @staticmethod
    def _deadline_passed(value: Any, today: date) -> bool:
        if not value:
            return False
        if isinstance(value, date):
            deadline = value
        else:
            deadline = date.fromisoformat(str(value))
        return deadline < today

    @staticmethod
    def _as_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item not in (None, "")]
        return [str(value)]
