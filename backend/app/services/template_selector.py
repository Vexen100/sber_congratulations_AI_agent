from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TemplateChoice:
    tone: str
    subject_template: str
    body_template: str


def choose_template(*, segment: str, event_type: str, title: str) -> TemplateChoice:
    seg = (segment or "standard").lower()
    et = (event_type or "").lower()

    if et == "birthday":
        if seg == "vip":
            return TemplateChoice(
                tone="official",
                subject_template="Поздравляем с днём рождения, {first_name}!",
                body_template=(
                    "{first_name} {last_name},\n\n"
                    "Примите наши искренние поздравления с днём рождения! "
                    "Желаем крепкого здоровья, уверенных решений и новых достижений.\n\n"
                    "С уважением,\nКоманда Сбер"
                ),
            )
        return TemplateChoice(
            tone="warm",
            subject_template="{first_name}, с днём рождения!",
            body_template=(
                "{first_name},\n\n"
                "Поздравляем с днём рождения! Пусть этот год принесёт вдохновение, "
                "яркие успехи и добрые поводы для радости.\n\n"
                "С уважением,\nКоманда Сбер"
            ),
        )

    # Holiday / manual (fallback)
    if seg == "vip":
        return TemplateChoice(
            tone="official",
            subject_template="Поздравление: {title}",
            body_template=(
                "{first_name} {last_name},\n\n"
                "Поздравляем вас с событием: «{title}». "
                "Желаем стабильного роста, надёжных партнёров и успешной реализации планов.\n\n"
                "С уважением,\nКоманда Сбер"
            ),
        )

    return TemplateChoice(
        tone="warm",
        subject_template="Поздравляем: {title}",
        body_template=(
            "{first_name},\n\n"
            "Поздравляем с «{title}»! Пусть впереди будет больше сильных проектов, "
            "удачных решений и приятных событий.\n\n"
            "С уважением,\nКоманда Сбер"
        ),
    )
