from __future__ import annotations

import pytest

from app.agent.llm_provider import LLMProviderError, parse_llm_json


def test_parse_llm_json_ok():
    content = (
        '{"tone":"warm","subject":"Поздравляем с событием!",'
        '"body":"Текст поздравления для клиента: желаем стабильного роста, сильных решений и удачных проектов. '
        "Пусть впереди будет больше поводов для гордости и уверенности в завтрашнем дне.\\n\\n"
        'С уважением, Сбер"}'
    )
    res = parse_llm_json(content)
    assert res.tone in {"warm", "official"}
    assert "Поздравляем" in res.subject
    assert "Сбер" in res.body


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        "[]",
        '{"tone":"warm","subject":"hi","body":"x"}',
        '{"tone":"???","subject":"Нормальная тема","body":"Достаточно длинный текст для прохождения проверки."}',
    ],
)
def test_parse_llm_json_bad(content):
    with pytest.raises(LLMProviderError):
        parse_llm_json(content)
