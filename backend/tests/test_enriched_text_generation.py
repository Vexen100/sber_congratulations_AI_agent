from __future__ import annotations

from app.agent.text_generator import generate_text
from app.services.template_selector import choose_template


def test_text_generator_uses_enriched_company_context():
    choice = choose_template(event_type="holiday", title="День финансиста")
    subject, body = generate_text(
        choice,
        context={
            "first_name": "Павел",
            "middle_name": "Игоревич",
            "last_name": "Сафронов",
            "company_name": "ЗАО ТехСтрой",
            "official_company_name": 'ЗАО "ТехСтрой"',
            "position": "Финансовый директор",
            "okved_name": "Строительство жилых и нежилых зданий",
        },
        title="День финансиста",
    )
    assert "День финансиста" in subject
    assert 'ЗАО "ТехСтрой"' in body
    assert "Строительство жилых и нежилых зданий" in body


def test_text_generator_uses_manual_business_context():
    choice = choose_template(
        event_type="manual",
        title="Желаем сильных продаж и новых клиентов",
    )
    subject, body = generate_text(
        choice,
        context={
            "first_name": "Алина",
            "middle_name": "Сергеевна",
            "last_name": "Громова",
            "company_name": 'ООО "Логистика-Профи"',
            "position": "Операционный директор",
            "manual_kind": "business_touchpoint",
            "focus_hint": "sales",
        },
        title="Желаем сильных продаж и новых клиентов",
    )
    assert "Желаем сильных продаж и новых клиентов" in subject
    assert "деловое взаимодействие" in body
    assert "клиентской базы" in body


def test_text_generator_uses_structured_holiday_context():
    choice = choose_template(
        event_type="holiday",
        title="День российского предпринимательства",
    )
    subject, body = generate_text(
        choice,
        context={
            "first_name": "Игорь",
            "middle_name": "Павлович",
            "last_name": "Романов",
            "company_name": 'ООО "Вектор"',
            "position": "Генеральный директор",
            "holiday_category": "business",
            "holiday_focus_hint": "growth",
            "holiday_prompt_hint": "Предпринимательская энергия, развитие бизнеса, новые возможности",
        },
        title="День российского предпринимательства",
    )
    assert "День российского предпринимательства" in subject
    assert "устойчивый рост" in body
    assert "деловые инициативы" in body


def test_text_generator_uses_female_respectful_greeting_without_surname():
    choice = choose_template(
        event_type="holiday",
        title="День финансиста",
    )
    subject, body = generate_text(
        choice,
        context={
            "first_name": "Ирина",
            "middle_name": "Владимировна",
            "last_name": "Соколова",
            "respectful_greeting": "Уважаемая Ирина Владимировна",
        },
        title="День финансиста",
    )
    # Warm template addresses by first name; surname stays out of the opening paragraph.
    first_para = body.split("\n\n", 1)[0]
    assert "Ирина" in first_para
    assert "Соколова" not in first_para
