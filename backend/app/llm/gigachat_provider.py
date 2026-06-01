from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.llm.errors import LLMError
from app.llm.provider import LLMResponse


@dataclass
class _AccessToken:
    value: str
    expires_at: dt.datetime

    def is_valid(self) -> bool:
        return self.expires_at > dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=60)


def _normalize_expires_at(expires_at: int | float) -> dt.datetime:
    ts = float(expires_at)
    if ts > 1e12:
        ts = ts / 1000.0
    return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc)


def _ssl_verify_param() -> bool | str:
    if not settings.gigachat_verify_ssl_certs:
        return False
    if settings.gigachat_ca_bundle_file:
        return settings.gigachat_ca_bundle_file
    return True


class GigaChatLLMProvider:
    def __init__(self) -> None:
        if not settings.gigachat_credentials:
            raise LLMError("GIGACHAT_CREDENTIALS is not set")
        self._token: _AccessToken | None = None

    async def _get_token(self) -> _AccessToken:
        if self._token and self._token.is_valid():
            return self._token

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
            "Authorization": f"Basic {settings.gigachat_credentials}",
        }
        data = {"scope": settings.gigachat_scope}
        timeout = float(settings.gigachat_timeout_sec)
        async with httpx.AsyncClient(timeout=timeout, verify=_ssl_verify_param()) as client:
            response = await client.post(settings.gigachat_oauth_url, headers=headers, data=data)
            response.raise_for_status()
            payload = response.json()

        try:
            token = str(payload["access_token"])
            expires_at = _normalize_expires_at(payload["expires_at"])
        except Exception as exc:
            raise LLMError(f"unexpected GigaChat oauth response: {payload}") from exc

        self._token = _AccessToken(value=token, expires_at=expires_at)
        return self._token

    async def generate_text(self, messages: list[dict], **kwargs) -> LLMResponse:
        token = await self._get_token()
        model_name = str(kwargs.get("model") or settings.gigachat_model)
        payload: dict = {
            "model": model_name,
            "messages": messages,
            "temperature": float(settings.gigachat_temperature or 0.3),
        }
        if settings.gigachat_max_tokens:
            payload["max_tokens"] = int(settings.gigachat_max_tokens)

        url = settings.gigachat_base_url.rstrip("/") + "/chat/completions"
        headers = {"Accept": "application/json", "Authorization": f"Bearer {token.value}"}
        async with httpx.AsyncClient(
            timeout=float(settings.gigachat_timeout_sec),
            verify=_ssl_verify_param(),
        ) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        try:
            content = str(data["choices"][0]["message"]["content"])
        except Exception as exc:
            raise LLMError(f"unexpected GigaChat chat response: {data}") from exc
        return LLMResponse(content=content, model_name=model_name)
