from __future__ import annotations

from app.agent.gigachat_providers import build_illustration_prompt


def test_gigachat_prompt_avoids_card_word_and_forbids_text():
    system, user = build_illustration_prompt(
        event_type="birthday",
        event_title="День рождения",
        recipient_line="Иван Тестов",
        company="ООО Пример",
    )
    low = (system + "\n" + user).lower()
    assert "открытк" not in low
    assert "без текста" in low or "никакого текста" in low
