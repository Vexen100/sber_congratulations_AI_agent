from __future__ import annotations

import datetime as dt

from app.agent.event_semantics import build_event_semantics
from app.agent.llm_prompts import build_system_prompt, build_user_prompt


def test_event_semantics_for_business_holiday():
    semantics = build_event_semantics(
        event_type="holiday",
        event_title="День российского предпринимательства",
        event_details={
            "holiday_tags": {
                "category": "business",
                "focus_hint": "growth",
                "prompt_hint": "Предпринимательская энергия, развитие бизнеса, новые возможности",
                "audience": "business",
                "tone_hint": "official",
            }
        },
        profession="management",
    )
    assert semantics.category == "business"
    assert semantics.focus_hint == "growth"
    assert semantics.tone_hint == "official"
    assert "развитие бизнеса" in semantics.prompt_hint.lower()
    assert "развит" in semantics.visual_theme.lower()


def test_event_semantics_for_manual_technology_touchpoint():
    semantics = build_event_semantics(
        event_type="manual",
        event_title="Желаем технологического роста и сильных решений",
        event_details={
            "manual_kind": "business_touchpoint",
            "focus_hint": "technology",
            "tone_hint": "warm",
        },
        profession="it",
    )
    assert semantics.category == "manual-business"
    assert semantics.focus_hint == "technology"
    assert "технолог" in semantics.prompt_hint.lower() or "партн" in semantics.prompt_hint.lower()
    assert (
        "инновац" in semantics.visual_theme.lower() or "технолог" in semantics.visual_theme.lower()
    )


def test_build_user_prompt_includes_event_semantics_block():
    prompt = build_user_prompt(
        event_type="holiday",
        event_title="День российского предпринимательства",
        event_date=dt.date(2026, 5, 26),
        facts={
            "first_name": "Ирина",
            "profession": "management",
            "company_name": "ООО Вектор",
        },
        tone_hint="official",
        event_details={
            "holiday_tags": {
                "category": "business",
                "focus_hint": "growth",
                "prompt_hint": "Предпринимательская энергия, развитие бизнеса, новые возможности",
                "audience": "business",
            }
        },
    )
    assert "СЕМАНТИКА ПОВОДА" in prompt
    assert "Категория: business" in prompt
    assert "Смысловой фокус: growth" in prompt
    assert "Предпринимательская энергия" in prompt
    assert "Ответ должен начинаться с символа {" in build_system_prompt()
    assert "Переносы между абзацами в body кодируй как \\n\\n" in prompt
