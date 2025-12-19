from __future__ import annotations

import base64
import datetime as dt
import re
import uuid
from dataclasses import dataclass

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings


class GigaChatError(RuntimeError):
    pass


def _normalize_expires_at(expires_at: int | float) -> dt.datetime:
    """GigaChat docs/examples show expires_at sometimes in ms, sometimes in seconds."""
    ts = float(expires_at)
    # heuristics: milliseconds are much larger than seconds
    if ts > 1e12:
        ts = ts / 1000.0
    return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc)


def _ssl_verify_param() -> bool | str:
    if not settings.gigachat_verify_ssl_certs:
        return False
    if settings.gigachat_ca_bundle_file:
        return settings.gigachat_ca_bundle_file
    return True


@dataclass
class AccessToken:
    value: str
    expires_at: dt.datetime

    def is_valid(self, *, skew_sec: int = 60) -> bool:
        return self.expires_at > (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=skew_sec))


# Match both formats: <img src="..." /> and <img src="..." fuse="true"/>
IMG_SRC_RE = re.compile(r"<img[^>]*\s+src=[\"']([^\"']+)[\"'][^>]*/?>", re.IGNORECASE)


def extract_img_file_id(message_content: str) -> str | None:
    """Extract image file_id from <img src=\"...\"> response content.

    Handles formats:
    - <img src="file_id" />
    - <img src="file_id" fuse="true"/>
    - <img src='file_id' />
    """
    if not message_content:
        return None
    m = IMG_SRC_RE.search(message_content)
    if not m:
        return None
    return m.group(1).strip()


class GigaChatClient:
    def __init__(self) -> None:
        if not settings.gigachat_credentials:
            raise GigaChatError("GIGACHAT_CREDENTIALS is not set")
        self._token: AccessToken | None = None

    async def _get_token(self) -> AccessToken:
        if self._token and self._token.is_valid():
            return self._token

        rq_uid = str(uuid.uuid4())
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": rq_uid,
            "Authorization": f"Basic {settings.gigachat_credentials}",
        }
        data = {"scope": settings.gigachat_scope}

        async with httpx.AsyncClient(
            timeout=float(settings.gigachat_timeout_sec), verify=_ssl_verify_param()
        ) as c:
            r = await c.post(settings.gigachat_oauth_url, headers=headers, data=data)
            r.raise_for_status()
            payload = r.json()

        try:
            token = str(payload["access_token"])
            expires_at = _normalize_expires_at(payload["expires_at"])
        except Exception as e:
            raise GigaChatError(f"unexpected oauth response: {payload}") from e

        self._token = AccessToken(value=token, expires_at=expires_at)
        return self._token

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=3))
    async def chat_completions(
        self,
        *,
        messages: list[dict],
        model: str | None = None,
        temperature: float | None = None,
        function_call: str | None = None,
        x_client_id: str | None = None,
        x_request_id: str | None = None,
        x_session_id: str | None = None,
    ) -> dict:
        token = await self._get_token()
        url = settings.gigachat_base_url.rstrip("/") + "/chat/completions"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token.value}",
        }
        if x_client_id:
            headers["X-Client-ID"] = x_client_id
        if x_request_id:
            headers["X-Request-ID"] = x_request_id
        if x_session_id:
            headers["X-Session-ID"] = x_session_id

        payload: dict = {
            "model": model or settings.gigachat_model,
            "messages": messages,
        }
        temp = temperature if temperature is not None else settings.gigachat_temperature
        if temp is not None and str(temp).strip() != "":
            payload["temperature"] = float(temp)
        if function_call:
            payload["function_call"] = function_call

        async with httpx.AsyncClient(
            timeout=float(settings.gigachat_timeout_sec), verify=_ssl_verify_param()
        ) as c:
            r = await c.post(url, headers=headers, json=payload)
            r.raise_for_status()
            return r.json()

    # Для скачивания изображений используем более длинный таймаут, но без повторных попыток,
    # чтобы не затягивать прогон слишком сильно.
    @retry(stop=stop_after_attempt(1), wait=wait_exponential(multiplier=0.5, min=0.5, max=3))
    async def download_file_content(self, *, file_id: str, x_client_id: str | None = None) -> bytes:
        token = await self._get_token()

        # Docs mention GET, some sources mention POST. We'll try GET first, then POST on 405.
        url = settings.gigachat_base_url.rstrip("/") + f"/files/{file_id}/content"
        headers = {"Authorization": f"Bearer {token.value}"}
        if x_client_id:
            headers["X-Client-ID"] = x_client_id

        async with httpx.AsyncClient(
            timeout=float(settings.gigachat_image_timeout_sec), verify=_ssl_verify_param()
        ) as c:
            r = await c.get(url, headers=headers)
            if r.status_code == 405:
                r = await c.post(url, headers=headers)
            r.raise_for_status()

            # Some SDKs return base64 content, some return raw bytes. Handle both.
            ct = (r.headers.get("content-type") or "").lower()
            if "application/json" in ct:
                obj = r.json()
                content = obj.get("content")
                if isinstance(content, str):
                    return base64.b64decode(content)
                raise GigaChatError(f"unexpected json file content: {obj}")

            raw = r.content
            try:
                # If it's base64 text, decode; else return raw bytes.
                if raw and all(chr(b).isascii() for b in raw[:50]):  # cheap heuristic
                    txt = raw.decode("utf-8").strip()
                    if re.fullmatch(r"[A-Za-z0-9+/=\s]+", txt) and len(txt) > 100:
                        return base64.b64decode(txt)
            except Exception:
                pass
            return raw
