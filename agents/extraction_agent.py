import re
import time
from datetime import date
from typing import Any

from agents.deadline_extraction_agent import DeadlineExtractionAgent
from agents.table_extraction_agent import TableExtractionAgent
from app.config import Settings, get_settings
from tools.extraction_llm import ExtractionLLM, coerce_extraction_llm
from tools.groq_tool import GroqClient
from tools.model_routing import ModelTask
from tools.prompt_budget import focus_text, truncate_text
from tools.prompt_loader import load_prompt, render_prompt


class OpportunityExtractionAgent:
    PAYMENT_TERMS = ("application fee", "processing fee", "pay fee", "payment required")

    def __init__(
        self,
        settings: Settings | None = None,
        client: GroqClient | ExtractionLLM | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.llm = coerce_extraction_llm(client, self.settings)
        self.deadline_agent = DeadlineExtractionAgent(self.settings, llm=self.llm)
        self.table_agent = TableExtractionAgent(self.settings, llm=self.llm)

    def extract(self, candidate: dict[str, Any]) -> dict[str, Any]:
        text = candidate.get("page_text") or candidate.get("snippet") or ""
        table_data = str(candidate.get("table_data") or "")
        deadline_payload = self.deadline_agent.extract(text)
        table_rows = self.table_agent.extract(table_data) if table_data else []
        opportunity = self._extract_opportunity(
            candidate=candidate,
            text=text,
            deadline_payload=deadline_payload,
            table_rows=table_rows,
        )
        if opportunity.get("is_opportunity") is False:
            raise ValueError("Page does not describe an opportunity.")
        normalized = self._normalize(opportunity, candidate, text)
        if candidate.get("content_type") == "link_only":
            normalized["extraction_notes"].append("Link-only source; details must be confirmed on the official page.")
        if normalized["payment_requested"]:
            normalized["warnings"].append("Listing appears to request payment; verify carefully before proceeding.")
        return normalized

    def _extract_opportunity(
        self,
        *,
        candidate: dict[str, Any],
        text: str,
        deadline_payload: dict[str, Any],
        table_rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        system = load_prompt("opportunity_extraction_system.txt")
        base_limit = min(self.settings.extraction_max_source_chars, self.settings.groq_max_input_chars)
        limits = [base_limit, max(800, base_limit // 2), max(500, base_limit // 4)]
        last_error: Exception | None = None
        for attempt, max_chars in enumerate(limits):
            focused = focus_text(text, max_chars)
            user = render_prompt(
                "opportunity_extraction_user.txt",
                source_url=str(candidate.get("source_url") or ""),
                title=truncate_text(str(candidate.get("title") or ""), 200),
                deadline_analysis=DeadlineExtractionAgent.format_for_prompt(deadline_payload),
                table_data=TableExtractionAgent.format_for_prompt(table_rows),
                content=focused,
            )
            try:
                return self.llm.json_chat(
                    task=ModelTask.OPPORTUNITY,
                    system=system,
                    user=user,
                    temperature=0.0,
                    max_retries=0 if attempt > 0 else self.settings.search_extraction_max_retries,
                )
            except RuntimeError as exc:
                last_error = exc
                message = str(exc)
                if "413" not in message and "429" not in message:
                    raise
                if attempt == len(limits) - 1:
                    raise
                wait = self._retry_wait_seconds(message, attempt)
                if wait > 0:
                    time.sleep(wait)
        if last_error:
            raise last_error
        raise RuntimeError("Opportunity extraction failed after prompt budget retries.")

    @staticmethod
    def _retry_wait_seconds(message: str, attempt: int) -> float:
        match = re.search(r"try again in ([\d.]+)s", message, re.IGNORECASE)
        if match:
            return min(float(match.group(1)) + 0.5, 20.0)
        return min(2.0 * (attempt + 1), 8.0)

    def _normalize(self, payload: dict[str, Any], candidate: dict[str, Any], text: str) -> dict[str, Any]:
        title = payload.get("title") or candidate.get("title")
        if not title:
            raise ValueError("Opportunity extraction returned no title.")
        deadline = self._normalize_deadline(payload.get("deadline"), payload.get("deadline_text"))
        eligibility = self._as_list(payload.get("eligibility_requirements") or payload.get("eligibility"))
        required_documents = self._as_list(payload.get("required_documents"))
        warnings = self._as_list(payload.get("warnings"))
        extraction_notes = self._as_list(payload.get("extraction_notes"))
        extraction_notes.extend(self._as_list(payload.get("benefits")))
        for label, value in (
            ("degree_level", payload.get("degree_level")),
            ("field_of_study", payload.get("field_of_study")),
            ("official_url", payload.get("official_url")),
            ("source_confidence", payload.get("source_confidence")),
            ("deadline_text", payload.get("deadline_text")),
        ):
            rendered = self._as_list(value)
            if rendered:
                extraction_notes.append(f"{label}: {', '.join(rendered)}")
        payment_requested = self._payment_requested(text, warnings)
        return {
            "title": str(title)[:240],
            "provider": payload.get("provider"),
            "country": payload.get("country") or payload.get("location"),
            "opportunity_type": payload.get("opportunity_type"),
            "deadline": deadline,
            "funding_type": payload.get("funding_type"),
            "eligibility": eligibility,
            "required_documents": required_documents,
            "application_url": payload.get("application_url") or payload.get("official_url") or candidate.get("source_url"),
            "contact_email": payload.get("contact_email"),
            "summary": str(payload.get("summary") or self._summary(text, candidate.get("snippet")))[:1000],
            "payment_requested": payment_requested,
            "warnings": warnings,
            "extraction_notes": extraction_notes,
        }

    @staticmethod
    def _normalize_deadline(deadline: object, deadline_text: object) -> str | None:
        if deadline and str(deadline).strip().lower() not in {"", "null", "none"}:
            try:
                parsed = date.fromisoformat(str(deadline)[:10])
            except ValueError:
                return None
            if parsed < date.today():
                return None
            return parsed.isoformat()
        return None

    @staticmethod
    def _as_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item not in (None, "")]
        return [str(value)]

    @staticmethod
    def _summary(text: str, snippet: str | None) -> str:
        source = text or snippet or ""
        return " ".join(source.split())[:500]

    def _payment_requested(self, text: str, warnings: list[str]) -> bool:
        lowered = text.lower()
        if any(term in lowered for term in self.PAYMENT_TERMS):
            return True
        return any("payment" in warning.lower() or "fee" in warning.lower() for warning in warnings)
