import json
import time
from typing import Any

import requests

from app.config import Settings, get_settings
from tools.observability_tool import model_rate_limiter, timed_api_call


class MistralClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = "https://api.mistral.ai/v1"
        self.max_retries = self.settings.max_model_retries

    def json_chat(
        self,
        *,
        model: str,
        system: str,
        user: str,
        temperature: float = 0.0,
        reasoning_effort: str | None = None,
    ) -> dict[str, Any]:
        content = self.chat(
            model=model,
            system=system,
            user=user,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
            response_format={"type": "json_object"},
        )
        return self._parse_json(content)

    def chat(
        self,
        *,
        model: str,
        system: str,
        user: str,
        temperature: float = 0.0,
        reasoning_effort: str | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if response_format:
            payload["response_format"] = response_format
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort

        with model_rate_limiter.slot():
            with timed_api_call(provider="mistral", endpoint="/chat/completions", model=model) as call:
                response = self._post_with_retries(f"{self.base_url}/chat/completions", payload)
                call["status_code"] = response.status_code
                call["success"] = response.ok
                if not response.ok:
                    call["error_message"] = response.text[:500]
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def embed(self, texts: list[str]) -> list[list[float]]:
        with model_rate_limiter.slot():
            with timed_api_call(provider="mistral", endpoint="/embeddings", model=self.settings.embed_model) as call:
                response = self._post_with_retries(
                    f"{self.base_url}/embeddings",
                    {"model": self.settings.embed_model, "input": texts},
                )
                call["status_code"] = response.status_code
                call["success"] = response.ok
                if not response.ok:
                    call["error_message"] = response.text[:500]
        response.raise_for_status()
        data = response.json()["data"]
        return [item["embedding"] for item in sorted(data, key=lambda item: item["index"])]

    def _post_with_retries(self, url: str, payload: dict[str, Any]) -> requests.Response:
        headers = {
            "Authorization": f"Bearer {self.settings.require_mistral()}",
            "Content-Type": "application/json",
        }
        response: requests.Response | None = None
        for attempt in range(self.max_retries + 1):
            response = requests.post(url, headers=headers, json=payload, timeout=self.settings.model_timeout_seconds)
            if response.status_code not in {429, 500, 502, 503, 504}:
                return response
            if attempt == self.max_retries:
                return response
            time.sleep(self._retry_delay(response, attempt))
        return response

    @staticmethod
    def _retry_delay(response: requests.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), 120.0)
            except ValueError:
                pass
        return min(2.0 * (2**attempt), 120.0)

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        text = content.strip()
        if text.startswith("```"):
            text = text.strip("`").removeprefix("json").strip()
        return json.loads(text)
