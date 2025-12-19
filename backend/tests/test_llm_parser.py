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


def test_parse_llm_json_from_markdown_code_block():
    # Test JSON wrapped in markdown code block (common LLM behavior)
    content_with_markdown = (
        "```json\n"
        '{"tone":"warm","subject":"Поздравляем с событием!",'
        '"body":"Текст поздравления для клиента: желаем стабильного роста, сильных решений и удачных проектов. '
        "Пусть впереди будет больше поводов для гордости и уверенности в завтрашнем дне.\\n\\n"
        'С уважением, Сбер"}\n'
        "```"
    )
    res = parse_llm_json(content_with_markdown)
    assert res.tone == "warm"
    assert "Поздравляем" in res.subject
    assert "Сбер" in res.body


def test_parse_llm_json_with_raw_newlines_inside_body_string():
    # Some providers return "almost JSON": raw newlines inside a quoted JSON string (INVALID JSON).
    # Our parser should repair it by escaping newlines inside string literals.
    content_with_raw_newlines = (
        "{\n"
        '  "tone": "warm",\n'
        '  "subject": "Тестовое поздравление",\n'
        '  "body": "Первая строка с достаточно длинным текстом, чтобы пройти минимальную валидацию. '
        'Добавляем еще немного текста для надежности.\n\nВторая строка — продолжение поздравления."\n'
        "}"
    )
    res = parse_llm_json(content_with_raw_newlines)
    assert res.tone == "warm"
    assert res.subject == "Тестовое поздравление"
    assert "Первая строка" in res.body
    assert "\n\n" in res.body


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
