from __future__ import annotations

import datetime as dt

from app.core.config import settings
from app.db.models import Client, Event, Greeting
from app.services.email_rendering import build_smtp_message
from app.services.sender import send_greeting


def test_build_smtp_message_contains_html_alternative(monkeypatch):
    greeting = Greeting(
        subject="Тестовое поздравление",
        body="Первый абзац.\n\nВторой абзац.",
        image_path=None,
    )

    msg = build_smtp_message(
        greeting=greeting,
        recipient="client@company.test",
        from_email="no-reply@sber.test",
    )

    assert msg.is_multipart()
    plain_part = msg.get_body(preferencelist=("plain",))
    html_part = msg.get_body(preferencelist=("html",))
    assert plain_part is not None
    assert html_part is not None
    assert "Первый абзац." in plain_part.get_content()
    assert "#0b6a49" in html_part.get_content()
    assert "Сбер | персональное поздравление" in html_part.get_content()
    assert "Тёплое поздравление от команды Сбера" in html_part.get_content()
    assert "Персональное поздравление для вас." in html_part.get_content()
    assert "Мы оформили это письмо в фирменной зелёной палитре" not in html_part.get_content()
    assert "AI-пайплайн Сбера" not in html_part.get_content()
    assert "Это письмо сформировано в рамках AI-конвейера" not in html_part.get_content()
    assert "color:#111111; font-weight:600;" in html_part.get_content()
    assert (
        "background:#f4f7f5; font-family:Arial, Helvetica, sans-serif;" in html_part.get_content()
    )
    assert "background:#ffffff; padding:34px 36px 36px;" in html_part.get_content()
    assert (
        "background:#ffffff; color:#123629; border:1px solid rgba(19, 109, 75, 0.10);"
        in html_part.get_content()
    )


async def test_send_greeting_via_smtp_uses_html_message(db_session, monkeypatch):
    captured: dict[str, object] = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout=None):  # noqa: D401, ANN001
            captured["host"] = host
            captured["port"] = port
            captured["timeout"] = timeout
            captured["instance"] = self

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: ANN001
            return False

        def starttls(self):
            captured["starttls"] = True

        def login(self, username, password):  # noqa: ANN001
            captured["login"] = (username, password)

        def send_message(self, msg):
            captured["message"] = msg

    monkeypatch.setattr(settings, "send_mode", "smtp", raising=False)
    monkeypatch.setattr(settings, "smtp_host", "smtp.company.test", raising=False)
    monkeypatch.setattr(settings, "smtp_port", 2525, raising=False)
    monkeypatch.setattr(settings, "smtp_starttls", True, raising=False)
    monkeypatch.setattr(settings, "smtp_ssl", False, raising=False)
    monkeypatch.setattr(settings, "smtp_allow_all_recipients", True, raising=False)
    monkeypatch.setattr(settings, "smtp_username", None, raising=False)
    monkeypatch.setattr(settings, "smtp_password", None, raising=False)
    monkeypatch.setattr(settings, "smtp_from_email", "hello@sber.test", raising=False)
    monkeypatch.setattr("app.services.sender.smtplib.SMTP", FakeSMTP)

    client = Client(
        first_name="Ирина",
        last_name="Соколова",
        email="irina@company.test",
        preferred_channel="email",
        birth_date=dt.date(1990, 1, 1),
        is_demo=False,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)

    event = Event(
        client_id=client.id,
        event_type="manual",
        event_date=dt.date.today(),
        title="Тест",
        details={},
    )
    db_session.add(event)
    await db_session.commit()
    await db_session.refresh(event)

    greeting = Greeting(
        event_id=event.id,
        client_id=client.id,
        tone="warm",
        subject="Сбер поздравляет",
        body="Первый абзац письма.\n\nВторой абзац письма.",
        image_path=None,
        status="generated",
    )
    db_session.add(greeting)
    await db_session.commit()
    await db_session.refresh(greeting)

    delivery = await send_greeting(
        db_session,
        greeting=greeting,
        recipient=client.email or "",
        client=client,
    )

    assert delivery.status == "sent"
    assert delivery.channel == "email"
    msg = captured["message"]
    assert msg.is_multipart()
    assert msg.get_body(preferencelist=("plain",)) is not None
    html_part = msg.get_body(preferencelist=("html",))
    assert html_part is not None
    html_content = html_part.get_content()
    assert "Сбер | персональное поздравление" in html_content
    assert "Сбер поздравляет" in html_content
    assert "Первый абзац письма." in html_content
    assert "Тёплое поздравление от команды Сбера" in html_content
    assert "Персональное поздравление для вас." in html_content
    assert "Это письмо сформировано в рамках AI-конвейера" not in html_content
    assert "AI-пайплайн Сбера" not in html_content
