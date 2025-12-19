from __future__ import annotations

from app.services.template_selector import TemplateChoice


def _extra_line(context: dict) -> str:
    company = context.get("company_name")
    position = context.get("position")

    bits: list[str] = []
    if company:
        bits.append(f"Успехов вашей команде в {company}.")
    if position:
        bits.append(f"Пусть работа в роли «{position}» приносит вдохновение и сильные результаты.")
    # Do not expose last interaction topic in greetings (privacy / tone). Keep generic gratitude.
    bits.append("Спасибо, что остаётесь с нами.")

    if not bits:
        return ""
    return "\n\n" + " ".join(bits)


def generate_text(choice: TemplateChoice, *, context: dict, title: str) -> tuple[str, str]:
    """Generate (subject, body).

    MVP: deterministic template rendering + small personalization line.
    (External LLM provider can be plugged later behind the same interface.)
    """

    subject = choice.subject_template.format(**context, title=title).strip()
    body = choice.body_template.format(**context, title=title).rstrip()
    body = body + _extra_line(context)
    return subject, body
