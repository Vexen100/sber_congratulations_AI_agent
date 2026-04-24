from __future__ import annotations

from app.agent.gigachat_client import GigaChatClient
from app.agent.gigachat_providers import GigaChatImageProvider, build_illustration_prompt
from app.core.config import settings


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
    assert "без людей" in low
    assert "шаров" in low or "шары" in low
    assert "торт" in low


def test_gigachat_prompt_uses_business_still_life_without_birthday_objects():
    system, user = build_illustration_prompt(
        event_type="holiday",
        event_title="День российского предпринимательства",
        recipient_line="Иван Тестов",
        company="ООО Вектор",
        event_details={
            "holiday_tags": {
                "category": "business",
                "focus_hint": "growth",
                "prompt_hint": "Предпринимательская энергия, развитие бизнеса, новые возможности",
                "audience": "business",
            }
        },
        profession="management",
    )
    low = (system + "\n" + user).lower()
    assert "открытк" not in low
    assert "премиальный деловой натюрморт" in low
    assert "подарочная коробка" in low
    assert "торт" not in user.lower()
    assert "шаров" not in user.lower()
    assert "без людей" in low
    assert "без офиса" in low


def test_gigachat_prompt_uses_new_year_specific_motif_without_birthday_objects():
    system, user = build_illustration_prompt(
        event_type="holiday",
        event_title="Новый год",
        recipient_line="Иван Тестов",
        company="ООО Вектор",
        event_details={"holiday_tags": {"focus_hint": "renewal", "category": "holiday"}},
        profession="management",
    )
    low = (system + "\n" + user).lower()
    assert "елов" in low
    assert "огни" in low
    assert "торт" not in user.lower()
    assert "воздуш" not in user.lower()


def test_gigachat_prompt_uses_march_8_flowers_without_birthday_objects():
    system, user = build_illustration_prompt(
        event_type="holiday",
        event_title="8 Марта",
        recipient_line="Ирина Тестова",
        company="ООО Вектор",
        event_details={"holiday_tags": {"focus_hint": "care", "category": "holiday"}},
        profession="management",
    )
    low = (system + "\n" + user).lower()
    assert "цвет" in low
    assert "торт" not in user.lower()
    assert "воздуш" not in user.lower()


async def test_gigachat_image_provider_uses_image_generation_timeout(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_chat_completions(self, **kwargs):
        captured["timeout_sec"] = kwargs.get("timeout_sec")
        return {"choices": [{"message": {"content": '<img src="file-123" />'}}]}

    async def fake_download_file_content(self, *, file_id: str, x_client_id: str | None = None):
        captured["file_id"] = file_id
        captured["x_client_id"] = x_client_id
        return b"jpg-bytes"

    monkeypatch.setattr(settings, "gigachat_credentials", "test-creds", raising=False)
    monkeypatch.setattr(settings, "gigachat_image_generation_timeout_sec", 123.0, raising=False)
    monkeypatch.setattr(GigaChatClient, "chat_completions", fake_chat_completions)
    monkeypatch.setattr(GigaChatClient, "download_file_content", fake_download_file_content)

    provider = GigaChatImageProvider()
    file_id, jpg = await provider.generate_jpg(
        system_style="style",
        prompt="prompt",
        x_client_id="42",
    )

    assert captured["timeout_sec"] == 123.0
    assert captured["file_id"] == "file-123"
    assert captured["x_client_id"] == "42"
    assert file_id == "file-123"
    assert jpg == b"jpg-bytes"
