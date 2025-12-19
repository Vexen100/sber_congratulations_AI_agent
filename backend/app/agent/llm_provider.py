from __future__ import annotations

import json
import re
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

    Handles cases where LLM wraps JSON in markdown code blocks (```json ... ```)
    or returns pretty-printed JSON with newlines.

    Raises LLMProviderError on invalid format.
    """
    content_original = content
    content = content.strip()

    def _repair_unescaped_newlines_in_json_strings(s: str) -> str:
        """Make 'almost JSON' valid JSON by escaping raw newlines inside string literals.

        Some providers return JSON-looking text where the value of "body" contains literal
        newlines inside quotes. This is INVALID JSON (newlines must be escaped as \\n).
        We repair it with a small state machine, without changing newlines outside strings.
        """
        out: list[str] = []
        in_str = False
        esc = False
        for ch in s:
            if in_str:
                if esc:
                    out.append(ch)
                    esc = False
                    continue
                if ch == "\\":
                    out.append(ch)
                    esc = True
                    continue
                if ch == '"':
                    out.append(ch)
                    in_str = False
                    continue
                if ch == "\n":
                    out.append("\\n")
                    continue
                if ch == "\r":
                    out.append("\\r")
                    continue
                out.append(ch)
                continue

            # outside string literal
            if ch == '"':
                out.append(ch)
                in_str = True
            else:
                out.append(ch)
        return "".join(out)

    def _try_parse(candidate: str) -> dict | None:
        # 1) strict parse
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict) and {"tone", "subject", "body"} <= set(obj.keys()):
                return obj
        except json.JSONDecodeError:
            pass

        # 2) repair common "almost-json" issue (raw newlines inside strings)
        try:
            repaired = _repair_unescaped_newlines_in_json_strings(candidate)
            obj = json.loads(repaired)
            if isinstance(obj, dict) and {"tone", "subject", "body"} <= set(obj.keys()):
                return obj
        except json.JSONDecodeError:
            return None
        return None

    # Try to find JSON in markdown code block: ```json ... ``` or ``` ... ```
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)```", content, re.DOTALL | re.IGNORECASE)
    if json_match:
        content = json_match.group(1).strip()

    # Try parsing as-is first (most common case - pretty-printed JSON is valid)
    obj = _try_parse(content)
    if obj is not None:
        return _validate_and_return(obj)

    # If direct parse failed, try to find JSON object in the content
    # Use a more sophisticated approach: find the first { and try to parse until matching }
    if not content.startswith("{"):
        # Try to find JSON object boundary more carefully
        start_idx = content.find("{")
        if start_idx >= 0:
            # Try to find matching closing brace
            brace_count = 0
            end_idx = start_idx
            for i in range(start_idx, len(content)):
                if content[i] == "{":
                    brace_count += 1
                elif content[i] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break
            if end_idx > start_idx:
                content = content[start_idx:end_idx]
                obj = _try_parse(content)
                if obj is not None:
                    return _validate_and_return(obj)

    # Last resort: try regex extraction (less reliable)
    json_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", content, re.DOTALL)
    if json_match:
        obj = _try_parse(json_match.group(0))
        if obj is not None:
            return _validate_and_return(obj)

    # If all parsing attempts failed, raise error with full content preview
    preview = content_original[:500] if len(content_original) > 500 else content_original
    raise LLMProviderError(
        f"LLM did not return valid JSON. Content preview (first 500 chars): {preview!r}"
    )


def _validate_and_return(obj: dict) -> LLMResult:
    """Validate parsed JSON object and return LLMResult."""
    tone = str(obj.get("tone", "")).strip()
    subject = str(obj.get("subject", "")).strip()
    body = str(obj.get("body", "")).strip()

    if tone not in {"official", "warm"}:
        tone = ""

    if not (6 <= len(subject) <= 80):
        raise LLMProviderError(f"subject length out of bounds: {len(subject)} (required: 6-80)")
    if not (100 <= len(body) <= 2000):
        raise LLMProviderError(f"body length out of bounds: {len(body)} (required: 100-2000)")

    return LLMResult(tone=tone or "warm", subject=subject, body=body)
