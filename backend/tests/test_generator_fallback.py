from __future__ import annotations

import datetime as dt

from app.agent.generator import generate_subject_body
from app.db.models import Client, Event
from app.services.template_selector import choose_template


class FakeLLM:
    def __init__(self, content: str):
        self._content = content

    async def generate(self, *, system: str, user: str) -> str:  # noqa: ARG002
        return self._content


async def test_generator_falls_back_on_invalid_llm_json(monkeypatch):
    # Force "LLM enabled" by monkeypatching provider factory used inside generator module.
    monkeypatch.setattr("app.agent.generator.get_llm_provider", lambda: FakeLLM("not json"))

    today = dt.date.today()
    c = Client(
        first_name="Иван",
        last_name="Тестов",
        segment="standard",
        email="ivan@example.com",
        preferred_channel="email",
        birth_date=dt.date(1990, 1, 1),
        company_name="Тест ООО",
        position="Директор",
    )
    ev = Event(
        client_id=1,
        event_type="manual",
        event_date=today,
        title="Тестовое событие",
        details={},
    )
    choice = choose_template(segment=c.segment, event_type=ev.event_type, title=ev.title)

    tone, subject, body = await generate_subject_body(
        event=ev, client=c, template_choice=choice, today=today
    )
    assert tone in {"warm", "official"}
    assert "Тестовое" in subject or "Поздрав" in subject
    assert "Сбер" in body


async def test_generator_uses_llm_when_valid(monkeypatch):
    monkeypatch.setattr(
        "app.agent.generator.get_llm_provider",
        lambda: FakeLLM(
            '{"tone":"official","subject":"Поздравляем, Иван!","body":"Иван Тестов, поздравляем с днём рождения! '
            "Желаем крепкого здоровья, уверенных решений и новых достижений в работе. "
            "Пусть этот год принесёт вдохновение, поддержку команды и яркие успехи.\\n\\n"
            'С уважением, Команда Сбер"}'
        ),
    )

    today = dt.date.today()
    c = Client(
        first_name="Иван",
        last_name="Тестов",
        segment="vip",
        email="ivan@example.com",
        preferred_channel="email",
        birth_date=dt.date(1990, 1, 1),
    )
    ev = Event(
        client_id=1,
        event_type="birthday",
        event_date=today,
        title="День рождения",
        details={},
    )
    choice = choose_template(segment=c.segment, event_type=ev.event_type, title=ev.title)

    tone, subject, body = await generate_subject_body(
        event=ev, client=c, template_choice=choice, today=today
    )
    assert tone == "official"
    assert subject == "Поздравляем, Иван!"
    assert "Команда Сбер" in body
