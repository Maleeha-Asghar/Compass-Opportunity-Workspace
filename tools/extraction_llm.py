import inspect
from typing import Any, Protocol

from app.config import Settings, get_settings
from tools.groq_tool import GroqClient
from tools.mistral_tool import MistralClient
from tools.model_routing import ModelTask


class JsonChatClient(Protocol):
    def json_chat(
        self,
        *,
        task: ModelTask,
        system: str,
        user: str,
        temperature: float = 0.0,
        model: str | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
    ) -> dict[str, Any]: ...


class ExtractionLLM:
    """Route extraction tasks to the best provider/model for cost and accuracy."""

    def __init__(self, settings: Settings | None = None, groq: GroqClient | None = None) -> None:
        self.settings = settings or get_settings()
        self._groq = groq or GroqClient(self.settings)
        self._mistral = MistralClient(self.settings) if self.settings.mistral_api_key else None

    def route(self, task: ModelTask) -> tuple[str, str]:
        if task == ModelTask.OPPORTUNITY and self.settings.extraction_prefers_mistral and self._mistral:
            return "mistral", self.settings.extraction_model
        return "groq", self.settings.fast_model

    @property
    def provider(self) -> str:
        return self.route(ModelTask.OPPORTUNITY)[0]

    @property
    def model(self) -> str:
        return self.route(ModelTask.OPPORTUNITY)[1]

    def json_chat(
        self,
        *,
        task: ModelTask = ModelTask.OPPORTUNITY,
        system: str,
        user: str,
        temperature: float = 0.0,
        model: str | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
    ) -> dict[str, Any]:
        provider, routed_model = self.route(task)
        chosen_model = model or routed_model
        if provider == "mistral" and self._mistral:
            return self._mistral.json_chat(
                model=chosen_model,
                system=system,
                user=user,
                temperature=temperature,
            )
        return self._groq.json_chat(
            model=chosen_model,
            system=system,
            user=user,
            temperature=temperature,
            timeout=timeout or self.settings.search_extraction_timeout_seconds,
            max_retries=max_retries if max_retries is not None else self.settings.search_extraction_max_retries,
        )


class LegacyJsonChatAdapter:
    """Adapt simple model-based clients to the task-routed extraction interface."""

    def __init__(self, client: Any, settings: Settings | None = None) -> None:
        self.client = client
        self.settings = settings or get_settings()

    def json_chat(
        self,
        *,
        task: ModelTask = ModelTask.OPPORTUNITY,
        system: str,
        user: str,
        temperature: float = 0.0,
        model: str | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
    ) -> dict[str, Any]:
        chosen_model = model or self._model_for_task(task)
        return self.client.json_chat(
            model=chosen_model,
            system=system,
            user=user,
            temperature=temperature,
            timeout=timeout,
            max_retries=max_retries,
        )

    def _model_for_task(self, task: ModelTask) -> str:
        if task == ModelTask.OPPORTUNITY and self.settings.extraction_prefers_mistral:
            return self.settings.extraction_model
        return self.settings.fast_model


def coerce_extraction_llm(
    client: Any | None,
    settings: Settings | None = None,
) -> ExtractionLLM | LegacyJsonChatAdapter | Any:
    if client is None:
        return ExtractionLLM(settings)
    if isinstance(client, ExtractionLLM):
        return client
    if isinstance(client, GroqClient):
        return ExtractionLLM(settings, groq=client)
    try:
        parameters = inspect.signature(client.json_chat).parameters
    except (AttributeError, TypeError, ValueError):
        return client
    if "task" in parameters:
        return client
    return LegacyJsonChatAdapter(client, settings)
