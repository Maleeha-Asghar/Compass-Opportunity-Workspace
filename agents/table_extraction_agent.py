import json
from typing import Any

from app.config import Settings, get_settings
from tools.extraction_llm import ExtractionLLM
from tools.model_routing import ModelTask
from tools.prompt_budget import truncate_text
from tools.prompt_loader import render_prompt


class TableExtractionAgent:
    def __init__(self, settings: Settings | None = None, llm: ExtractionLLM | None = None) -> None:
        self.settings = settings or get_settings()
        self.llm = llm or ExtractionLLM(self.settings)

    def extract(self, table_data: str) -> list[dict[str, Any]]:
        table_data = table_data.strip()
        if not table_data:
            return []
        user = render_prompt(
            "table_extraction_prompt.txt",
            table_data=truncate_text(table_data, self.settings.extraction_max_source_chars),
        )
        payload = self.llm.json_chat(
            task=ModelTask.TABLE,
            system="You extract structured rows from tables. Return JSON only.",
            user=user,
            temperature=0.0,
        )
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        rows = payload.get("rows")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
        return []

    @staticmethod
    def format_for_prompt(rows: list[dict[str, Any]], *, max_chars: int = 1200) -> str:
        if not rows:
            return "None found."
        return truncate_text(json.dumps(rows, ensure_ascii=False), max_chars)
