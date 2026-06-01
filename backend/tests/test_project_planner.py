from __future__ import annotations

import datetime as dt
import zipfile

import httpx
import pytest

from app.core.config import settings
from app.db.session import get_session
from app.llm.provider import LLMResponse
from app.main import create_app
from app.project_planner.docx_export import _generated_at_text, export_project_report_docx
from app.project_planner.generator import generate_project_report
from app.project_planner.mock_generator import build_mock_report
from app.project_planner.schemas import ProjectPlannerInput
from app.project_planner.validators import build_clarifications, validate_project_report


def _payload() -> ProjectPlannerInput:
    return ProjectPlannerInput(
        idea="Провести фестиваль талантов в Уральском банке с региональным охватом",
        deadline=dt.date.today() + dt.timedelta(days=90),
        budget=1_500_000,
        geography="Свердловская область",
        stakeholders="HR, руководители направлений, сотрудники банка",
        current_resources="Команда внутренних коммуникаций и площадки банка",
        technology_constraints="Использовать только согласованные внутренние каналы",
        project_accents="Учесть 185-летие Сбера и идеи фестиваля 2023 года",
    )


class FakeBadProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_text(self, messages: list[dict], **kwargs) -> LLMResponse:  # noqa: ARG002
        self.calls += 1
        return LLMResponse(content="not json", model_name="fake-bad")


class FakeErrorProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_text(self, messages: list[dict], **kwargs) -> LLMResponse:  # noqa: ARG002
        self.calls += 1
        raise RuntimeError("fake provider is unavailable")


def _build_test_client(db_session):
    app = create_app()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    return app, client


def _docx_text(path) -> str:
    from docx import Document

    document = Document(path)
    chunks = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            chunks.extend(cell.text for cell in row.cells)
    return "\n".join(chunks)


def test_project_planner_clarifications_allow_assumptions_after_default_limit():
    payload = ProjectPlannerInput(idea="коротко", questions_asked_count=3)
    response = build_clarifications(payload)
    assert response.can_generate_with_assumptions is True
    assert response.default_limit == 3


def test_mock_report_is_valid_and_contains_source_input():
    payload = _payload()
    report = build_mock_report(payload)
    assert report.source_input.project_accents == payload.project_accents
    assert len(report.roadmap) >= 4
    assert len(report.concepts) == 3
    assert not validate_project_report(report)


def test_docx_export_creates_zip_document(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "project_planner_docx_dir", str(tmp_path), raising=False)
    report = build_mock_report(_payload())
    path = export_project_report_docx(report, run_id=42)
    assert path.exists()
    assert zipfile.is_zipfile(path)


def test_docx_export_contains_demo_ready_sections(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "project_planner_docx_dir", str(tmp_path), raising=False)
    report = build_mock_report(_payload())
    path = export_project_report_docx(report, run_id=43)

    text = _docx_text(path)

    assert "Дата генерации" in text
    assert "Оценка является предварительной" in text
    assert "Целевая аудитория" in text
    assert "Риски паспорта проекта" in text
    assert "Gantt-like представление" in text
    assert "RACI" in text
    assert "Факторы трудоёмкости" in text
    assert "Сценарий защиты" in text


@pytest.mark.parametrize("tz_value", [None, "", object(), "No/Such_Timezone"])
def test_docx_generated_at_falls_back_for_invalid_timezone(tz_value, monkeypatch):
    monkeypatch.setattr(settings, "tz", tz_value, raising=False)

    generated_at = _generated_at_text()

    assert generated_at
    assert len(generated_at) == 16


def test_validate_project_report_warns_on_milestone_count_outside_required_range():
    report = build_mock_report(_payload())
    report.roadmap[0].milestones = report.roadmap[0].milestones[:2]
    report.roadmap[1].milestones = report.roadmap[1].milestones * 3

    warnings = validate_project_report(report)

    assert any("меньше 3 контрольных точек" in warning for warning in warnings)
    assert any("больше 6 контрольных точек" in warning for warning in warnings)


async def test_generator_falls_back_on_invalid_fake_llm(monkeypatch):
    monkeypatch.setattr(settings, "project_planner_use_mock_llm", False, raising=False)
    monkeypatch.setattr(settings, "gigachat_retry_count", 1, raising=False)
    provider = FakeBadProvider()
    report, model_name, used_fallback = await generate_project_report(
        _payload(),
        provider=provider,
    )
    assert used_fallback is True
    assert model_name == "fallback"
    assert provider.calls == 2
    assert report.passport.title
    assert any("fallback" in warning.lower() for warning in report.warnings)


async def test_generator_falls_back_without_credentials_when_mock_disabled(monkeypatch):
    monkeypatch.setattr(settings, "project_planner_use_mock_llm", False, raising=False)
    monkeypatch.setattr(settings, "gigachat_credentials", None, raising=False)

    report, model_name, used_fallback = await generate_project_report(_payload())

    assert used_fallback is True
    assert model_name == "fallback"
    assert report.passport.title
    assert any("GigaChat не настроен" in warning for warning in report.warnings)


async def test_generator_falls_back_on_provider_error_without_retrying_network(monkeypatch):
    monkeypatch.setattr(settings, "project_planner_use_mock_llm", False, raising=False)
    provider = FakeErrorProvider()

    report, model_name, used_fallback = await generate_project_report(
        _payload(),
        provider=provider,
    )

    assert used_fallback is True
    assert model_name == "fallback"
    assert provider.calls == 1
    assert report.passport.title
    assert any("fake provider is unavailable" in warning for warning in report.warnings)


async def test_gigachat_provider_uses_env_model_with_fake_httpx(monkeypatch):
    from app.llm.gigachat_provider import GigaChatLLMProvider
    import app.llm.gigachat_provider as gigachat_provider

    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    class FakeAsyncClient:
        calls: list[dict] = []

        def __init__(self, **kwargs) -> None:  # noqa: ARG002
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
            return None

        async def post(self, url: str, headers=None, data=None, json=None):  # noqa: ANN001
            self.calls.append({"url": url, "headers": headers, "data": data, "json": json})
            if url == settings.gigachat_oauth_url:
                return FakeResponse(
                    {"access_token": "fake-token", "expires_at": 4_102_444_800_000}
                )
            return FakeResponse({"choices": [{"message": {"content": "{\"ok\": true}"}}]})

    monkeypatch.setattr(settings, "gigachat_credentials", "fake-credentials", raising=False)
    monkeypatch.setattr(settings, "gigachat_model", "FakeGigaChatModel", raising=False)
    monkeypatch.setattr(gigachat_provider.httpx, "AsyncClient", FakeAsyncClient)

    provider = GigaChatLLMProvider()
    response = await provider.generate_text([{"role": "user", "content": "ping"}])

    assert response.content == '{"ok": true}'
    assert response.model_name == "FakeGigaChatModel"
    assert FakeAsyncClient.calls[0]["headers"]["Authorization"] == "Basic fake-credentials"
    assert FakeAsyncClient.calls[1]["headers"]["Authorization"] == "Bearer fake-token"
    assert FakeAsyncClient.calls[1]["json"]["model"] == "FakeGigaChatModel"


async def test_project_planner_api_respects_generate_with_assumptions_flag(db_session):
    app, client = _build_test_client(db_session)
    incomplete_payload = ProjectPlannerInput(idea="коротко").model_dump(mode="json")

    async with client:
        blocked_resp = await client.post(
            "/api/project-planner/runs",
            json={"input": incomplete_payload, "generate_with_assumptions": False},
        )
        empty_list_resp = await client.get("/api/project-planner/runs")
        allowed_resp = await client.post(
            "/api/project-planner/runs",
            json={"input": incomplete_payload, "generate_with_assumptions": True},
        )
    app.dependency_overrides.clear()

    assert blocked_resp.status_code == 422
    assert "Недостаточно исходных данных" in blocked_resp.json()["detail"]
    assert empty_list_resp.status_code == 200
    assert empty_list_resp.json() == []
    assert allowed_resp.status_code == 200
    allowed_run = allowed_resp.json()["run"]
    assert allowed_run["has_docx"] is True
    assert allowed_run["assumptions"]


async def test_project_planner_api_create_list_detail_and_docx(db_session):
    app, client = _build_test_client(db_session)
    payload = _payload().model_dump(mode="json")

    async with client:
        clarify_resp = await client.post("/api/project-planner/clarifications", json=payload)
        create_resp = await client.post(
            "/api/project-planner/runs",
            json={"input": payload, "generate_with_assumptions": False},
        )
        list_resp = await client.get("/api/project-planner/runs")
    app.dependency_overrides.clear()

    assert clarify_resp.status_code == 200
    assert create_resp.status_code == 200
    assert list_resp.status_code == 200

    run = create_resp.json()["run"]
    assert run["report"]["source_input"]["project_accents"] == payload["project_accents"]
    assert run["has_docx"] is True
    assert all("file_path" not in artifact for artifact in run["artifacts"])
    assert list_resp.json()[0]["id"] == run["id"]

    app, client = _build_test_client(db_session)
    async with client:
        detail_resp = await client.get(f"/api/project-planner/runs/{run['id']}")
        docx_resp = await client.get(f"/api/project-planner/runs/{run['id']}/docx")
    app.dependency_overrides.clear()

    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == run["id"]
    assert all("file_path" not in artifact for artifact in detail_resp.json()["artifacts"])
    assert docx_resp.status_code == 200
    assert docx_resp.content.startswith(b"PK")
