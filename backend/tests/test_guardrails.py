from __future__ import annotations

import pytest

from app.services.guardrails import validate_message_text


def test_validate_message_text_allows_clean_text():
    validate_message_text("Уважаемый клиент, поздравляем с профессиональным праздником!")


@pytest.mark.parametrize(
    "bad_fragment",
    ["паспорт", "номер карты", "CVV", "Pin"],
)
def test_validate_message_text_blocks_sensitive_content(bad_fragment: str):
    with pytest.raises(ValueError, match="forbidden substring detected"):
        validate_message_text(f"В тексте случайно упомянут {bad_fragment}")
