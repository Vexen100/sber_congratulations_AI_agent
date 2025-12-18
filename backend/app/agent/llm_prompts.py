from __future__ import annotations

import datetime as dt


def build_system_prompt() -> str:
    return (
        "Ты помощник Сбербанка, который готовит персональные поздравления клиентам.\n"
        "Критично:\n"
        "- Используй ТОЛЬКО факты из блока FACTS (не выдумывай компанию, достижения, проекты).\n"
        "- Не добавляй и не запрашивай чувствительные данные (паспорт, номера карт, PIN/CVV и т.п.).\n"
        "- Тон: деловой/тёплый, без фамильярности, без политических/спорных тем.\n"
        "- Выводи РОВНО JSON без markdown и без лишнего текста.\n"
    )


def build_user_prompt(
    *,
    event_type: str,
    event_title: str,
    event_date: dt.date,
    segment: str,
    facts: dict,
) -> str:
    # Facts is already a dict of allowed fields (first_name, last_name, company, position, last_interaction, etc.)
    return (
        "Сгенерируй поздравление.\n\n"
        "FACTS (только это можно использовать):\n"
        f"{facts}\n\n"
        "CONTEXT:\n"
        f"- event_type: {event_type}\n"
        f"- event_title: {event_title}\n"
        f"- event_date: {event_date.isoformat()}\n"
        f"- client_segment: {segment}\n\n"
        "REQUIREMENTS:\n"
        "- subject: 6..80 символов\n"
        "- body: 300..900 символов, 2-4 абзаца, без списков\n"
        "- Добавь 1-2 фразы персонализации на основе FACTS (если данных нет — пропусти)\n"
        "- Не упоминай 'ИИ', 'модель', 'промпт', внутренние процессы\n\n"
        "OUTPUT JSON schema:\n"
        "{\n"
        '  "tone": "official|warm",\n'
        '  "subject": "string",\n'
        '  "body": "string"\n'
        "}\n"
    )
