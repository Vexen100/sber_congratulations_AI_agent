from __future__ import annotations

from app.agent.gigachat_client import GigaChatClient, GigaChatError, extract_img_file_id


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
        except Exception as e:
            raise GigaChatError(f"unexpected chat response: {data}") from e

        file_id = extract_img_file_id(content)
        if not file_id:
            raise GigaChatError(f"image file_id not found in content: {content!r}")

        jpg = await self._client.download_file_content(file_id=file_id, x_client_id=x_client_id)
        return file_id, jpg


def build_card_image_prompt(
    *, event_title: str, recipient_line: str, company: str | None
) -> tuple[str, str]:
    # Keep prompt deterministic and brand-safe; avoid hallucinated facts.
    style = (
        "Ты — дизайнер поздравительных открыток в фирменном стиле Сбера. "
        "Минимализм, современная графика, зелёные оттенки, без текста мелким шрифтом, без логотипов сторонних компаний. "
        "Не добавляй персональные данные кроме имени."
    )
    who = recipient_line.strip()
    extra = f" Компания: {company}." if company else ""
    prompt = (
        f"Сгенерируй поздравительную открытку (JPG), событие: {event_title}. "
        f"Получатель: {who}.{extra} "
        "Открытка должна быть позитивной и деловой."
    )
    return style, prompt
