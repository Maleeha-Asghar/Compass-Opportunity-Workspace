from typing import Any

from app.config import Settings, get_settings
from tools.mistral_tool import MistralClient


class EmbeddingTool:
    def __init__(self, settings: Settings | None = None, client: MistralClient | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = client or MistralClient(self.settings)

    def opportunity_text(self, opportunity: dict[str, Any]) -> str:
        parts = [
            opportunity.get("title"),
            opportunity.get("provider"),
            opportunity.get("country"),
            opportunity.get("opportunity_type"),
            opportunity.get("funding_type"),
            opportunity.get("summary"),
        ]
        return " ".join(str(part) for part in parts if part)

    def embed_opportunity(self, opportunity: dict[str, Any]) -> list[float]:
        return self.client.embed([self.opportunity_text(opportunity)])[0]
