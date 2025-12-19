from __future__ import annotations

import logging

from app.agent.gigachat_client import GigaChatClient, GigaChatError, extract_img_file_id

log = logging.getLogger(__name__)


class GigaChatTextProvider:
    def __init__(self) -> None:
        self._client = GigaChatClient()

    async def generate(self, *, system: str, user: str) -> str:
        data = await self._client.chat_completions(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
        )
        try:
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise GigaChatError(f"unexpected chat response: {data}") from e


class GigaChatImageProvider:
    def __init__(self) -> None:
        self._client = GigaChatClient()

    async def generate_jpg(
        self,
        *,
        system_style: str,
        prompt: str,
        x_client_id: str | None = None,
    ) -> tuple[str, bytes]:
        """Return (file_id, jpg_bytes)."""
        log.debug(
            "GigaChat image generation request: system_style=%s prompt=%s",
            system_style[:100] if len(system_style) > 100 else system_style,
            prompt[:100] if len(prompt) > 100 else prompt,
        )
        data = await self._client.chat_completions(
            messages=[
                {"role": "system", "content": system_style},
                {"role": "user", "content": prompt},
            ],
            function_call="auto",
            x_client_id=x_client_id,
        )
        try:
            content = data["choices"][0]["message"]["content"]
            finish_reason = data["choices"][0].get("finish_reason", "unknown")
            log.debug(
                "GigaChat chat_completions response: finish_reason=%s content=%s",
                finish_reason,
                content[:200] if len(content) > 200 else content,
            )
        except Exception as e:
            log.error("GigaChat chat_completions unexpected response: %s", data)
            raise GigaChatError(f"unexpected chat response: {data}") from e

        file_id = extract_img_file_id(content)
        if not file_id:
            log.error(
                "GigaChat image file_id not found in content. "
                "Full content: %s. Full response: %s",
                content,
                data,
            )
            raise GigaChatError(
                f"image file_id not found in content: {content!r}. "
                f"finish_reason={data.get('choices', [{}])[0].get('finish_reason', 'unknown')}"
            )

        log.debug("GigaChat extracted file_id=%s, downloading...", file_id)
        jpg = await self._client.download_file_content(file_id=file_id, x_client_id=x_client_id)
        log.debug("GigaChat downloaded file_id=%s, size=%d bytes", file_id, len(jpg))
        return file_id, jpg


def _visual_theme(*, event_type: str, event_title: str) -> str:
    t = (event_title or "").lower()
    et = (event_type or "").lower()
    if et == "birthday" or "день рождения" in t:
        return (
            "натюрморт: воздушные шары, праздничный торт со свечами (без надписей), конфетти, "
            "тёплый свет, атмосфера праздника"
        )
    if "новый год" in t or "с наступающим" in t:
        return "зимний уют: огни гирлянд, ель, подарки (без надписей), снежные огоньки, тёплый интерьер"
    if "8 марта" in t:
        return "весенние цветы: тюльпаны/пионы, мягкий свет, чистый фон, без надписей и открыток"
    if et == "holiday":
        return "абстрактная праздничная иллюстрация: свет, символы успеха, аккуратный минимализм, без надписей"
    return "минималистичная деловая иллюстрация: свет, динамика, успех, без надписей"


def build_illustration_prompt(
    *, event_type: str, event_title: str, recipient_line: str, company: str | None
) -> tuple[str, str]:
    """Build prompt for a *text-free illustration* (NOT a greeting card).

    Avoid the word 'открытка' to reduce the model's tendency to place text.

    Uses direct "Нарисуй" command format as per GigaChat docs examples.
    """
    style = (
        "Ты — художник, создающий изображения для поздравлений.\n"
        "Стиль: современная фотореалистичная иллюстрация/фото-стиль, зелёные оттенки (ассоциация со Сбером), минимализм.\n"
        "КРИТИЧЕСКИ ВАЖНО: НИКАКОГО ТЕКСТА на изображении — 0 букв, 0 слов, 0 цифр, 0 водяных знаков, 0 логотипов, 0 табличек.\n"
        "Запрет также на надписи на предметах: торт, шары, упаковки, вывески.\n"
        "Никаких рамок, макетов, декоративных элементов с текстом.\n"
        "Только чистая иллюстрация/фото без текста.\n"
    )
    theme = _visual_theme(event_type=event_type, event_title=event_title)
    # Use direct "Нарисуй" command as per GigaChat docs - simpler and more reliable
    # Don't include recipient/company in main prompt to keep it simple and direct
    prompt = f"Нарисуй {theme}."
    return style, prompt
