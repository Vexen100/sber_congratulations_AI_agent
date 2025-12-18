from __future__ import annotations

import json
from dataclasses import dataclass

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.agent.gigachat_providers import GigaChatTextProvider
from app.core.config import settings


@dataclass(frozen=True)
class LLMResult:
    tone: str
    subject: str
    body: str


class LLMProviderError(RuntimeError):
    pass


class BaseLLMProvider:
    async def generate(self, *, system: str, user: str) -> str:
        raise NotImplementedError


class OpenAICompatibleProvider(BaseLLMProvider):
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise LLMProviderError("OPENAI_API_KEY is not set")
        self._base_url = settings.openai_base_url.rstrip("/")
        self._model = settings.openai_model
        self._temperature = float(settings.openai_temperature)
        self._timeout = float(settings.openai_timeout_sec)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=3))
    async def generate(self, *, system: str, user: str) -> str:
        url = f"{self._base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
        payload = {
            "model": self._model,
            "temperature": self._temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()

        try:
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise LLMProviderError(f"unexpected response shape: {data}") from e


def get_llm_provider() -> BaseLLMProvider | None:
    mode = (settings.llm_mode or "template").lower()
    if mode == "openai":
        if not settings.openai_api_key:
            return None
        return OpenAICompatibleProvider()
    if mode == "gigachat":
        if not settings.gigachat_credentials:
            return None

        # Wrap into BaseLLMProvider interface
        class _Adapter(BaseLLMProvider):
            def __init__(self) -> None:
                self._p = GigaChatTextProvider()

            async def generate(self, *, system: str, user: str) -> str:
                return await self._p.generate(system=system, user=user)

        return _Adapter()
    return None


def parse_llm_json(content: str) -> LLMResult:
    """Parse strict JSON output from LLM into a structured result.

    Raises LLMProviderError on invalid format.
    """
    try:
        obj = json.loads(content)
    except Exception as e:
        raise LLMProviderError("LLM did not return valid JSON") from e

    if not isinstance(obj, dict):
        raise LLMProviderError("LLM JSON must be an object")

    tone = str(obj.get("tone", "")).strip()
    subject = str(obj.get("subject", "")).strip()
    body = str(obj.get("body", "")).strip()

    if tone not in {"official", "warm"}:
        # tolerate missing tone by defaulting later, but reject garbage
        tone = ""

    if not (6 <= len(subject) <= 80):
        raise LLMProviderError("subject length out of bounds")
    if not (100 <= len(body) <= 2000):
        raise LLMProviderError("body length out of bounds")

    return LLMResult(tone=tone or "warm", subject=subject, body=body)
