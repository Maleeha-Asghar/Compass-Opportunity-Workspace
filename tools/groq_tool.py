"""Groq API client for LLM interactions."""
import json
import re
import time
from typing import Any

import requests

from app.config import Settings, get_settings
from tools.observability_tool import model_rate_limiter, timed_api_call


class GroqClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = "https://api.groq.com/openai/v1"
        self.max_retries = self.settings.max_model_retries

    def json_chat(
        self,
        *,
        model: str,
        system: str,
        user: str,
        temperature: float = 0.0,
        reasoning_effort: str | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
    ) -> dict[str, Any]:
        # Groq doesn't support response_format, but we enforce JSON in the system prompt
        # The agents already have "Return strict JSON" in their system prompts
        content = self.chat(
            model=model,
            system=system,
            user=user,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
            timeout=timeout,
            max_retries=max_retries,
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
        timeout: int | None = None,
        max_retries: int | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
    
        with model_rate_limiter.slot():
            with timed_api_call(provider="groq", endpoint="/chat/completions", model=model) as call:
                response = self._post_with_retries(
                    f"{self.base_url}/chat/completions",
                    payload,
                    timeout=timeout,
                    max_retries=max_retries,
                )
                call["status_code"] = response.status_code
                call["success"] = response.status_code == 200
                if response.status_code != 200:
                    call["error_message"] = response.text[:500]
        
        if response.status_code != 200:
            error_detail = response.text
            try:
                error_detail = response.json().get("error", {}).get("message", error_detail)
            except:
                pass
            raise RuntimeError(f"Groq API error ({response.status_code}): {error_detail}")
        
        return response.json()["choices"][0]["message"]["content"]

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Note: Groq doesn't provide embedding API. Use alternative if needed."""
        raise NotImplementedError("Groq does not provide embedding API. Use MistralClient for embeddings or implement alternative.")

    def _post_with_retries(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        timeout: int | None = None,
        max_retries: int | None = None,
    ) -> requests.Response:
        headers = {
            "Authorization": f"Bearer {self.settings.require_groq()}",
            "Content-Type": "application/json",
        }
        request_timeout = timeout if timeout is not None else self.settings.model_timeout_seconds
        retry_limit = max_retries if max_retries is not None else self.max_retries
        response: requests.Response | None = None
        for attempt in range(retry_limit + 1):
            response = requests.post(url, headers=headers, json=payload, timeout=request_timeout)
            if response.status_code == 429:
                wait = self._rate_limit_wait_seconds(response)
                if wait is not None and wait <= 45 and attempt < retry_limit:
                    time.sleep(wait)
                    continue
                return response
            if response.status_code not in {500, 502, 503, 504}:
                return response
            if attempt == retry_limit:
                return response
            time.sleep(self._retry_delay(response, attempt))
        return response

    @staticmethod
    def _rate_limit_wait_seconds(response: requests.Response) -> float | None:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
        match = re.search(r"try again in ([\d.]+)s", response.text, re.IGNORECASE)
        if match:
            return float(match.group(1))
        return None

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
        if not text:
            raise ValueError("Empty response from API")

        fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if fence:
            text = fence.group(1).strip()

        if not text.startswith("{"):
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                text = json_match.group()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            if start == -1:
                raise
            parsed, _ = json.JSONDecoder().raw_decode(text[start:])
            if not isinstance(parsed, dict):
                raise ValueError("Groq JSON response must be an object.")
            return parsed
