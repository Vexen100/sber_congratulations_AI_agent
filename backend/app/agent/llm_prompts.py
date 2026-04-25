from __future__ import annotations

import datetime as dt

from app.agent.event_semantics import build_event_semantics


def build_system_prompt() -> str:
    return (
        "Ты эксперт по созданию персональных поздравлений от Сбербанка для клиентов.\n"
        "Твоя задача — создать уникальное, тёплое и содержательное поздравление, которое демонстрирует "
        "индивидуальный подход к каждому клиенту.\n\n"
        "КРИТИЧЕСКИ ВАЖНЫЕ ПРАВИЛА:\n"
        "- Используй ТОЛЬКО факты из блока FACTS (не выдумывай детали о компании, достижениях, проектах, истории сотрудничества).\n"
        "- Имя/отчество: используй только то, что есть в FACTS. Если отчество пустое/отсутствует — НЕ придумывай его.\n"
        "- В обращении НЕ используй фамилию клиента. Для нормального делового обращения используй имя + отчество, если отчество известно.\n"
        "- Если gender_hint=female, используй форму «Уважаемая ...», если gender_hint=male — «Уважаемый ...».\n"
        "- Если есть official_company_name / okved_name / ceo_name / company_site — используй их аккуратно и только по делу.\n"
        "- Никогда не придумывай ИНН, ОКВЭД, руководство компании или отрасль, если эти поля не переданы.\n"
        "- Не добавляй и не запрашивай чувствительные данные (паспорт, номера карт, PIN/CVV и т.п.).\n"
        "- Тон: деловой/тёплый в зависимости от типа праздника и подсказок в промпте, без фамильярности, без политических/спорных тем.\n"
        "- Не упоминай тему/вид последнего взаимодействия с клиентом; используй только общую благодарность за сотрудничество.\n"
        "- Каждое поздравление должно быть УНИКАЛЬНЫМ — избегай шаблонных фраз и одинаковых начал.\n"
        "- Проверь грамматику, пунктуацию и согласование в русском языке.\n"
        "- Выводи РОВНО JSON без markdown и без лишнего текста.\n"
        "- Ответ должен начинаться с символа { и заканчиваться символом }.\n"
        "- В поле body используй escaped-переносы \\n\\n внутри JSON-строки, а НЕ реальные переводы строк внутри кавычек.\n"
        "- Не добавляй пояснения до или после JSON.\n"
    )


def build_user_prompt(
    *,
    event_type: str,
    event_title: str,
    event_date: dt.date,
    facts: dict,
    tone_hint: str | None = None,
    event_details: dict | None = None,
) -> str:
    """Build user prompt for greeting generation.

    Args:
        event_type: birthday|holiday|manual
        event_title: название события
        event_date: дата события
        facts: словарь с фактами о клиенте
        tone_hint: подсказка тона из holiday_tags (official|warm), если есть
    """
    semantics = build_event_semantics(
        event_type=event_type,
        event_title=event_title,
        event_details=event_details or {},
        profession=(facts or {}).get("profession"),
    )

    tone_guidance = ""
    if tone_hint:
        if tone_hint.lower() == "official":
            tone_guidance = "Рекомендуемый тон: official (деловой, уважительный)."
        elif tone_hint.lower() == "warm":
            tone_guidance = "Рекомендуемый тон: warm (тёплый, дружелюбный)."
    else:
        tone_guidance = "Используй тёплый тон (warm), но оставайся профессиональным."

    personalization_guidance = ""
    if event_type.lower() == "birthday":
        personalization_guidance = (
            "ПЕРСОНАЛИЗАЦИЯ для дня рождения:\n"
            "- Используй имя и отчество ТОЛЬКО если отчество дано в FACTS (middle_name).\n"
            "- Если middle_name пустое/отсутствует: обращайся по имени, но НЕ используй фамилию в конце обращения и НЕ выдумывай отчество.\n"
            "- В официальном обращении ориентируйся на `respectful_greeting`, если оно передано в FACTS.\n"
            "- Если известна компания: упомяни успехи в работе, но БЕЗ конкретных проектов/цифр.\n"
            "- Если известна должность: свяжи пожелания с профессиональным развитием, но БЕЗ выдуманных деталей.\n"
            "- Если известен okved_name: можно аккуратно связать пожелание с отраслью, без канцелярита и без узкоспециальных деталей.\n"
            "- Добавь пожелания, которые подходят именно этому человеку (здоровье, успех в делах, гармония).\n"
        )
    else:
        personalization_guidance = (
            "ПЕРСОНАЛИЗАЦИЯ для праздника:\n"
            "- Адаптируй поздравление под конкретный праздник, учитывая его суть и значение.\n"
            "- Используй имя клиента естественно, не перегружая.\n"
            "- Если известна компания: свяжи пожелания с бизнес-контекстом, но БЕЗ конкретных проектов.\n"
            "- Если известна должность: учитывай профессиональную роль, но БЕЗ выдуманных достижений.\n"
            "- Если есть official_company_name или okved_name: используй их как источник более точной отраслевой персонализации.\n"
            "- Для каждого праздника найди уникальный угол: что он значит для бизнеса/личности.\n"
            "- В прямом обращении не ставь фамилию после имени или имени-отчества.\n"
        )
        if event_type.lower() == "holiday":
            details = event_details or {}
            holiday_tags = details.get("holiday_tags", {}) or {}
            category = holiday_tags.get("category")
            focus_hint = holiday_tags.get("focus_hint")
            prompt_hint = holiday_tags.get("prompt_hint")
            audience = holiday_tags.get("audience")
            holiday_lines = ["ДОПОЛНИТЕЛЬНЫЙ КОНТЕКСТ для holiday-события:\n"]
            if category:
                holiday_lines.append(f"- Категория праздника: {category}.\n")
            if audience:
                holiday_lines.append(f"- Аудитория повода: {audience}.\n")
            if focus_hint:
                holiday_lines.append(f"- Смысловой фокус пожеланий: {focus_hint}.\n")
            if prompt_hint:
                holiday_lines.append(f"- Семантика повода: {prompt_hint}.\n")
            holiday_lines.append(
                "- В тексте должна чувствоваться именно природа этого праздника, а не универсальный шаблон для любого случая.\n"
            )
            personalization_guidance += "".join(holiday_lines)
        if event_type.lower() == "manual":
            details = event_details or {}
            manual_kind = details.get("manual_kind")
            focus_hint = details.get("focus_hint")
            manual_lines = [
                "ДОПОЛНИТЕЛЬНЫЙ КОНТЕКСТ для manual-события:\n",
                "- Это управляемый деловой повод, а не календарный праздник.\n",
                "- Делай акцент на уважении, партнёрстве, развитии бизнеса и роли клиента.\n",
            ]
            if manual_kind:
                manual_lines.append(f"- Тип делового сценария: {manual_kind}.\n")
            if focus_hint:
                manual_lines.append(f"- Бизнес-фокус сценария: {focus_hint}.\n")
            manual_lines.append(
                "- Не придумывай достижения, цифры, сделки или конкретные совместные проекты, если их нет в FACTS.\n"
            )
            personalization_guidance += "".join(manual_lines)

    prompt_parts = [
        "Сгенерируй персональное поздравление от Сбербанка.\n\n",
        "FACTS о клиенте (используй ТОЛЬКО эти данные, не выдумывай ничего):\n",
        f"{facts}\n\n",
        "КОНТЕКСТ события:\n",
        f"- Тип события: {event_type}\n",
        f"- Название: {event_title}\n",
        f"- Дата: {event_date.isoformat()}\n",
        f"- {tone_guidance}\n\n",
        "СЕМАНТИКА ПОВОДА:\n",
        f"- Категория: {semantics.category}\n",
        f"- Смысловой фокус: {semantics.focus_hint}\n",
        f"- Семантическая подсказка: {semantics.prompt_hint}\n",
        f"- Guidance для текста: {semantics.greeting_guidance}\n\n",
        personalization_guidance,
        "\nТРЕБОВАНИЯ к тексту (ОБЯЗАТЕЛЬНО соблюдай):\n",
        "- subject: 6..80 символов, привлекательный заголовок с упоминанием праздника\n",
        "- body: МИНИМУМ 450 символов (целевой диапазон 600-900 символов, максимум 1200), 3-5 абзацев, без списков\n",
        "  КРИТИЧЕСКИ ВАЖНО: body должен быть НЕ МЕНЕЕ 450 символов. Короткие тексты (менее 450 символов) НЕДОПУСТИМЫ.\n",
        "- Структура body:\n",
        "  • Открытие: уникальное вступление (НЕ шаблонное «Поздравляем с...»)\n",
        "  • Основная часть: персонализированные пожелания, связанные с FACTS (2-3 абзаца)\n",
        "  • Заключение: благодарность «Спасибо, что остаётесь с нами» (без упоминания тем последних контактов)\n",
        "- РАЗНООБРАЗИЕ: каждый текст должен быть уникальным — используй разные формулировки, начинай по-разному\n",
        "- ЕСТЕСТВЕННОСТЬ: текст должен звучать как написанный человеком, не как шаблон\n",
        "- РЕЛЕВАНТНОСТЬ: адаптируй поздравление под конкретный праздник (Новый год, 8 Марта, день рождения и т.д.)\n",
        "- НЕ упоминай: 'ИИ', 'модель', 'промпт', внутренние процессы, конкретные банковские продукты\n\n",
        "ФОРМАТ ОТВЕТА:\n",
        "- Верни ОДИН JSON-объект и ничего больше.\n",
        "- Переносы между абзацами в body кодируй как \\n\\n, а не как реальные новые строки внутри JSON.\n",
        "- Не используй markdown-блоки ```json.\n\n",
        "OUTPUT JSON schema:\n",
        "{\n",
        '  "tone": "official|warm",\n',
        '  "subject": "string",\n',
        '  "body": "string"\n',
        "}\n",
    ]

    return "".join(prompt_parts)


def build_user_prompt_with_examples(
    *,
    event_type: str,
    event_title: str,
    event_date: dt.date,
    facts: dict,
    examples: str | None = None,
    tone_hint: str | None = None,
    event_details: dict | None = None,
) -> str:
    base_prompt = build_user_prompt(
        event_type=event_type,
        event_title=event_title,
        event_date=event_date,
        facts=facts,
        tone_hint=tone_hint,
        event_details=event_details,
    )

    extra = (examples or "").strip()
    if extra:
        # Keep base prompt first; examples are a soft steering block.
        return base_prompt + "\n\n" + extra + "\n"

    return base_prompt
