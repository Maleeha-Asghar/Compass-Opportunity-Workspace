from typing import Any

from app.config import Settings, get_settings


class LLMRegistry:
    """Lazy LLM factory so local development works without provider keys."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._cache: dict[str, Any] = {}

    def chat(self, role: str) -> Any | None:
        if not self._settings.llm_enabled:
            return None
        if role not in self._cache:
            self._cache[role] = self._build_chat_model(role)
        return self._cache[role]

    def _build_chat_model(self, role: str) -> Any:
        try:
            from langchain_mistralai import ChatMistralAI
        except ImportError as exc:
            raise RuntimeError(
                "langchain-mistralai is required for live LLM calls. Install requirements.txt."
            ) from exc

        if role == "router":
            return ChatMistralAI(model=self._settings.fast_model, temperature=0.0)
        if role == "draft":
            return ChatMistralAI(model=self._settings.fast_model, temperature=0.4)
        if role == "vision":
            return ChatMistralAI(
                model=self._settings.fast_model,
                temperature=0.0,
                model_kwargs={"reasoning_effort": "none"},
            )
        if role == "grounding":
            return ChatMistralAI(
                model=self._settings.fast_model,
                temperature=0.0,
                model_kwargs={"reasoning_effort": "none"},
            )
        return ChatMistralAI(model=self._settings.fast_model, temperature=0.1)


llms = LLMRegistry()
