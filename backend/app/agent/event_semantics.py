from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EventSemantics:
    category: str
    focus_hint: str
    tone_hint: str | None
    audience: str
    prompt_hint: str
    greeting_guidance: str
    visual_theme: str


_FOCUS_TO_GUIDANCE: dict[str, tuple[str, str]] = {
    "celebration": (
        "Подчеркни личную значимость момента, уважение к человеку и тёплую атмосферу праздника.",
        "праздничный натюрморт: воздушные шары, торт без надписей, мягкий свет, живое ощущение радости",
    ),
    "respect": (
        "Сделай акцент на уважении, достоинстве, надёжности и уверенном профессиональном пути.",
        "сдержанная торжественная иллюстрация: мягкий свет, благородные акценты, чистая композиция, без текста",
    ),
    "care": (
        "Сделай пожелания мягкими, человечными, уважительными и тёплыми.",
        "светлая тёплая иллюстрация: весенние цветы, мягкие оттенки, спокойная атмосфера, без текста",
    ),
    "team": (
        "Подчеркни силу команды, поддержку, слаженность и общее движение к результату.",
        "деловая командная иллюстрация: свет, динамика, современное пространство, ощущение совместной работы, без текста",
    ),
    "gratitude": (
        "Сделай акцент на благодарности, уважении и значимости повода без излишнего пафоса.",
        "торжественная спокойная иллюстрация: мягкий свет, глубина, благородные детали, без текста",
    ),
    "growth": (
        "Подчеркни развитие, новые возможности, масштаб и движение вперёд.",
        "деловая иллюстрация роста: современный город, свет, динамика, ощущение развития и перспективы, без текста",
    ),
    "stability": (
        "Сделай акцент на устойчивости, надёжности, точности и уверенных решениях.",
        "минималистичная деловая иллюстрация: чистые линии, устойчивые формы, спокойный зелёный свет, без текста",
    ),
    "finance": (
        "Подчеркни финансовую устойчивость, точность, взвешенность и уверенное развитие.",
        "деловая финансовая иллюстрация: абстрактные графики без цифр, свет, аккуратная геометрия, без текста",
    ),
    "technology": (
        "Подчеркни технологии, новые решения, гибкость мышления и современность.",
        "технологичная иллюстрация: цифровой свет, современный офисный минимализм, ощущение инноваций, без текста",
    ),
    "sales": (
        "Подчеркни доверие клиентов, коммуникацию, рост результата и сильные переговоры.",
        "деловая иллюстрация коммуникации и роста: динамика, свет, современная бизнес-среда, без текста",
    ),
    "operations": (
        "Подчеркни надёжность процессов, устойчивую работу системы и сильную организацию.",
        "операционная деловая иллюстрация: порядок, логистика, чёткая структура, без текста",
    ),
    "leadership": (
        "Подчеркни лидерство, управленческие решения и развитие команды.",
        "деловая лидерская иллюстрация: современное пространство, уверенная композиция, свет, без текста",
    ),
    "renewal": (
        "Подчеркни новый этап, обновление, сильный старт и хорошие ожидания от будущего.",
        "сезонная праздничная иллюстрация: свет, уют, ощущение обновления и нового цикла, без текста",
    ),
}


def _focus_bundle(
    focus_hint: str | None,
    *,
    fallback_focus: str,
    fallback_prompt: str,
    fallback_visual: str,
) -> tuple[str, str, str]:
    key = (focus_hint or "").strip().lower() or fallback_focus
    guidance, visual = _FOCUS_TO_GUIDANCE.get(key, (fallback_prompt, fallback_visual))
    return key, guidance, visual


def build_event_semantics(
    *,
    event_type: str,
    event_title: str,
    event_details: dict | None = None,
    profession: str | None = None,
) -> EventSemantics:
    et = (event_type or "").strip().lower()
    title = (event_title or "").strip()
    details = event_details or {}
    prof = (profession or "").strip().lower()

    if et == "birthday":
        focus, guidance, visual = _focus_bundle(
            "celebration",
            fallback_focus="celebration",
            fallback_prompt="Сделай акцент на личном празднике и тёплой атмосфере.",
            fallback_visual="праздничная иллюстрация дня рождения без текста",
        )
        return EventSemantics(
            category="personal",
            focus_hint=focus,
            tone_hint="warm",
            audience="individual",
            prompt_hint="Личный праздник, уважение к человеку, тёплая энергия и хорошие пожелания.",
            greeting_guidance=guidance,
            visual_theme=visual,
        )

    if et == "manual":
        focus_hint = details.get("focus_hint") or {
            "finance": "finance",
            "accounting": "finance",
            "logistics": "operations",
            "sales": "sales",
            "it": "technology",
            "hr": "team",
            "marketing": "growth",
            "construction": "operations",
            "medicine": "care",
            "security": "stability",
            "management": "leadership",
        }.get(prof, "growth")
        focus, guidance, visual = _focus_bundle(
            focus_hint,
            fallback_focus="growth",
            fallback_prompt="Сделай акцент на развитии бизнеса, уважении и партнёрстве.",
            fallback_visual="деловая иллюстрация партнёрства и роста без текста",
        )
        return EventSemantics(
            category="manual-business",
            focus_hint=focus,
            tone_hint=details.get("tone_hint") or "warm",
            audience="business",
            prompt_hint=(
                details.get("prompt_hint")
                or "Управляемый деловой повод: уважение, партнёрство, развитие бизнеса и значимость роли клиента."
            ),
            greeting_guidance=guidance,
            visual_theme=visual,
        )

    holiday_tags = details.get("holiday_tags", {}) or {}
    inferred_focus = holiday_tags.get("focus_hint")
    if not inferred_focus:
        title_low = title.lower()
        if "новый год" in title_low:
            inferred_focus = "renewal"
        elif "8 марта" in title_low:
            inferred_focus = "care"
        else:
            inferred_focus = "growth"
    focus, guidance, visual = _focus_bundle(
        inferred_focus,
        fallback_focus="growth",
        fallback_prompt="Сделай акцент на значимости праздника и его деловом или человеческом смысле.",
        fallback_visual="праздничная деловая иллюстрация без текста",
    )
    return EventSemantics(
        category=str(holiday_tags.get("category") or "holiday"),
        focus_hint=focus,
        tone_hint=holiday_tags.get("tone_hint") or "warm",
        audience=str(holiday_tags.get("audience") or "all"),
        prompt_hint=str(
            holiday_tags.get("prompt_hint")
            or f"Праздник «{title}»: нужно уловить его смысл и сделать пожелания не универсальными, а релевантными поводу."
        ),
        greeting_guidance=guidance,
        visual_theme=visual,
    )
