from __future__ import annotations

from app.agent.text_generator import generate_text
from app.services.template_selector import choose_template


def test_text_generator_does_not_echo_last_interaction():
    choice = choose_template(segment="standard", event_type="birthday", title="День рождения")
    subject, body = generate_text(
        choice,
        context={
            "first_name": "Ирина",
            "last_name": "Соколова",
            "company_name": "ООО Альфа-Логистика",
            "position": "Генеральный директор",
            "segment": "vip",
            "last_interaction_summary": "обсуждали условия РКО",
        },
        title="День рождения",
    )
    assert "обсуждали" not in body
    assert "Спасибо, что остаётесь с нами" in body
    assert subject
