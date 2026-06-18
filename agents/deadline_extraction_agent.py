import json
from typing import Any

from app.config import Settings, get_settings
from tools.extraction_llm import ExtractionLLM
from tools.model_routing import ModelTask, has_date_signals
from tools.prompt_budget import focus_text, truncate_text
from tools.prompt_loader import render_prompt


class DeadlineExtractionAgent:
    def __init__(self, settings: Settings | None = None, llm: ExtractionLLM | None = None) -> None:
        self.settings = settings or get_settings()
        self.llm = llm or ExtractionLLM(self.settings)

    def extract(self, text: str) -> dict[str, Any]:
        focused = focus_text(text, self.settings.extraction_max_source_chars)
        if not focused.strip():
            return {"deadlines": []}
        if self.settings.extraction_skip_deadline_without_dates and not has_date_signals(focused):
            return {"deadlines": []}
        user = render_prompt("deadline_extraction_prompt.txt", content=focused)
        payload = self.llm.json_chat(
            task=ModelTask.DEADLINE,
            system="You are a deadline extraction agent. Return JSON only.",
            user=user,
            temperature=0.0,
        )
        deadlines = payload.get("deadlines")
        if not isinstance(deadlines, list):
            return {"deadlines": []}
        return {"deadlines": deadlines}

    @staticmethod
    def format_for_prompt(deadline_payload: dict[str, Any], *, max_chars: int = 1200) -> str:
        if not deadline_payload.get("deadlines"):
            return "None found."
        return truncate_text(json.dumps(deadline_payload, ensure_ascii=False), max_chars)
