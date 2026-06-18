import base64
import json
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings


class ImageExtractionAgent:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def extract_from_image(self, image_path: str | Path, mime_type: str) -> dict[str, Any]:
        try:
            from langchain_core.messages import HumanMessage
            from langchain_mistralai import ChatMistralAI
        except ImportError as exc:
            raise RuntimeError("langchain-mistralai and langchain-core are required for image extraction.") from exc

        encoded = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
        llm = ChatMistralAI(
            model=self.settings.fast_model,
            temperature=0.0,
            api_key=self.settings.require_mistral(),
            model_kwargs={"reasoning_effort": "high"},
        )
        message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": (
                        "Extract scholarship, internship, fellowship, research, or assistantship details "
                        "from this poster/screenshot. Return strict JSON with keys: is_opportunity, title, "
                        "provider, country, deadline, funding_type, eligibility, required_documents, "
                        "contact_email, application_url, payment_requested, warnings. Use null or [] when unknown. "
                        "Do not invent missing details."
                    ),
                },
                {"type": "image_url", "image_url": f"data:{mime_type};base64,{encoded}"},
            ]
        )
        response = llm.invoke([message])
        return self._parse_json(str(response.content))

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.removeprefix("json").strip()
        return json.loads(cleaned)
