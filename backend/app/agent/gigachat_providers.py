from __future__ import annotations

import logging

from app.agent.event_semantics import build_event_semantics
from app.agent.gigachat_client import GigaChatClient, GigaChatError, extract_img_file_id
from app.core.config import settings

log = logging.getLogger(__name__)


def _illustration_scene_brief(
    *,
    event_type: str,
    event_title: str,
    semantics_category: str,
    semantics_focus: str,
    audience: str,
) -> str:
    title_low = (event_title or "").strip().lower()
    category = (semantics_category or "").strip().lower()
    focus = (semantics_focus or "").strip().lower()
    target_audience = (audience or "").strip().lower()

    if (event_type or "").strip().lower() == "birthday":
        return (
            "аккуратный праздничный натюрморт: торт без надписей, несколько воздушных шаров, "
            "подарочная коробка, мягкий свет, чистый белый или светлый фон"
        )

    if "новый год" in title_low:
        return (
            "новогодний натюрморт: еловые ветви, тёплые огни, ёлочные украшения, подарочная коробка, "
            "уютная зимняя атмосфера, светлый фон"
        )

    if "8 марта" in title_low:
        return (
            "светлая весенняя композиция: элегантный букет цветов, ленты, подарочная коробка, "
            "мягкий естественный свет, чистый светлый фон"
        )

    if "23 февраля" in title_low:
        return (
            "сдержанная торжественная композиция: подарочная коробка, благородный зелёный и графитовый декор, "
            "аккуратные праздничные элементы, мягкий свет, светлый фон"
        )

    if "1 мая" in title_low or "праздник весны и труда" in title_low:
        return (
            "первомайский весенний натюрморт (без людей): свежая зелень и весенние цветы, "
            "аккуратные рабочие символы без брендов (например, минималистичный садовый инструмент без рук), "
            "светлая праздничная композиция, мягкий естественный свет, чистый светлый фон, "
            "сдержанные зелёные акценты"
        )

    if category == "manual-business" or category == "business" or target_audience == "business":
        return (
            "премиальный деловой натюрморт: подарочная коробка, минималистичный декор, стеклянные и металлические акценты, "
            "чистая композиция, мягкий студийный свет, светлый фон"
        )

    if focus == "care":
        return (
            "тёплая праздничная композиция: цветы, подарочная коробка, мягкие ленты, "
            "спокойный свет, чистый светлый фон"
        )

    if focus == "renewal":
        return (
            "сезонный праздничный натюрморт: свет, обновление, декоративные ветви, подарочная коробка, "
            "чистый светлый фон"
        )

    return (
        "универсальный праздничный натюрморт: подарочная коробка, аккуратный декор, мягкий свет, "
        "сдержанные зелёные акценты, чистый светлый фон"
    )


class GigaChatTextProvider:
    def __init__(self) -> None:
        self._client = GigaChatClient()

    async def generate(self, *, system: str, user: str) -> str:
        data = await self._client.chat_completions(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=(
                float(settings.gigachat_temperature)
                if settings.gigachat_temperature is not None
                else 0.1
            ),
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
            timeout_sec=float(settings.gigachat_image_generation_timeout_sec),
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
                "GigaChat image file_id not found in content. Full content: %s. Full response: %s",
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


def build_illustration_prompt(
    *,
    event_type: str,
    event_title: str,
    recipient_line: str,
    company: str | None,
    event_details: dict | None = None,
    profession: str | None = None,
) -> tuple[str, str]:
    """Build prompt for a text-free celebratory still life with event-specific presets."""
    style = (
        "Ты создаёшь простую и аккуратную поздравительную иллюстрацию.\n"
        "Стиль: минималистичный праздничный натюрморт, чистая композиция, светлый фон, мягкий студийный свет, сдержанные зелёные акценты.\n"
        "Используй только предметную композицию без сюжетных сцен и без людей.\n"
        "КРИТИЧЕСКИ ВАЖНО: никаких людей, лиц, рук, силуэтов, толпы, детей, персонажей, животных.\n"
        "КРИТИЧЕСКИ ВАЖНО: никакого текста — 0 букв, 0 слов, 0 цифр, 0 логотипов, 0 вывесок, 0 водяных знаков.\n"
        "Запрещены офисные сцены, город, переговоры, командные сцены, интерьер с людьми и любые сюжетные персонажи.\n"
        "Если повод не связан с днём рождения, не добавляй торт и воздушные шары.\n"
        "Нужна только чистая праздничная иллюстрация без текста и без людей.\n"
    )
    semantics = build_event_semantics(
        event_type=event_type,
        event_title=event_title,
        event_details=event_details or {},
        profession=profession,
    )
    scene_brief = _illustration_scene_brief(
        event_type=event_type,
        event_title=event_title,
        semantics_category=semantics.category,
        semantics_focus=semantics.focus_hint,
        audience=semantics.audience,
    )
    prompt = (
        f"Нарисуй простую праздничную иллюстрацию для повода «{event_title}»: {scene_brief}. "
        f"Смысловой акцент: {semantics.prompt_hint}. "
        "Без людей, без лиц, без рук, без толпы, без офиса, без города, без текста."
    )
    return style, prompt
