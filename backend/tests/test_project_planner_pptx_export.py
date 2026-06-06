from __future__ import annotations

import datetime as dt
import zipfile
from io import BytesIO

import httpx
import pytest
from sqlalchemy import func, select

import app.project_planner.service as project_service
from app.db.session import get_session
from app.main import create_app
from app.project_planner.mock_generator import build_mock_report
from app.project_planner.models import ProjectArtifact, ProjectPlannerRun, ProjectRequest
from app.project_planner.pptx_export import (
    BUDGET_CAVEAT,
    PPTX_MEDIA_TYPE,
    export_project_report_pptx,
)
from app.project_planner.schemas import ProjectPlannerInput, ProjectReport


def _payload() -> ProjectPlannerInput:
    return ProjectPlannerInput(
        idea="Провести фестиваль талантов в Уральском банке",
        deadline=dt.date.today() + dt.timedelta(days=90),
        budget=1_500_000,
        geography="Свердловская область",
        stakeholders="HR, руководители направлений, сотрудники банка",
        current_resources="Команда внутренних коммуникаций и площадки банка",
        technology_constraints="Использовать только согласованные внутренние каналы",
        project_accents="Учесть 185-летие Сбера и идеи фестиваля 2023 года",
    )


def _report() -> ProjectReport:
    return build_mock_report(_payload())


def _pptx_zip(content: bytes) -> zipfile.ZipFile:
    return zipfile.ZipFile(BytesIO(content))


def _slide_xml_text(content: bytes) -> str:
    with _pptx_zip(content) as archive:
        parts = sorted(name for name in archive.namelist() if name.startswith("ppt/slides/slide"))
        return "\n".join(archive.read(name).decode("utf-8") for name in parts)


def _slide_count(content: bytes) -> int:
    with _pptx_zip(content) as archive:
        return len(
            [
                name
                for name in archive.namelist()
                if name.startswith("ppt/slides/slide") and name.endswith(".xml")
            ]
        )


def _assert_no_technical_dump(xml: str) -> None:
    assert "Traceback" not in xml
    assert "ValidationError" not in xml
    assert "Field required" not in xml
    assert "backend" not in xml
    assert "demo/reference" not in xml
    assert "Project Planner demo/reference budget catalog v1" not in xml
    assert "Источник: Встроенный demo/reference каталог MVP; каталог:" not in xml


def _build_test_client(db_session):
    app = create_app()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    return app, client


async def _insert_run(db_session, report: ProjectReport) -> int:
    payload = report.source_input
    request = ProjectRequest(
        idea=payload.idea,
        deadline=payload.deadline,
        budget=payload.budget,
        geography=payload.geography,
        stakeholders=payload.stakeholders,
        current_resources=payload.current_resources,
        technology_constraints=payload.technology_constraints,
        project_accents=payload.project_accents,
    )
    db_session.add(request)
    await db_session.commit()
    await db_session.refresh(request)

    run = ProjectPlannerRun(
        request_id=request.id,
        status="success",
        model_name="mock",
        result_json=report.model_dump(mode="json"),
        warnings_json=[],
        assumptions_json=[],
        finished_at=dt.datetime.now(dt.timezone.utc),
    )
    db_session.add(run)
    await db_session.commit()
    await db_session.refresh(run)
    return run.id


async def _count_rows(db_session, model) -> int:
    return (await db_session.execute(select(func.count()).select_from(model))).scalar_one()


def test_pptx_export_returns_valid_zip_presentation():
    content = export_project_report_pptx(_report())

    assert content.startswith(b"PK")
    with _pptx_zip(content) as archive:
        names = set(archive.namelist())
    assert "[Content_Types].xml" in names
    assert "ppt/presentation.xml" in names
    assert 5 <= _slide_count(content) <= 7


def test_pptx_export_contains_key_project_sections():
    report = _report()
    content = export_project_report_pptx(report)
    xml = _slide_xml_text(content)

    assert report.passport.title in xml
    assert "Презентация для защиты проекта" in xml
    assert "Проектная инициатива" in xml
    assert "Зачем проект нужен" in xml
    assert "Предлагаемое решение" in xml
    assert "Рекомендуем к реализации" in xml
    assert "Почему этот вариант" in xml
    assert "Как реализуем" in xml
    assert "Инвестиции и ресурсы" in xml
    assert "Что нужно для запуска" in xml
    assert "Следующий шаг" in xml
    assert "Утвердить концепцию, ответственных и бюджетную рамку." in xml
    assert "Полная матрица RACI — в DOCX." in xml
    assert "Следующий шаг: утвердить концепцию" not in xml
    assert "Закрываем презентацию решением" not in xml
    assert report.recommended_concept.concept_name in xml
    assert report.roadmap[0].name in xml
    assert BUDGET_CAVEAT in xml
    _assert_no_technical_dump(xml)


def test_pptx_export_truncates_long_text_without_technical_dump():
    report = _report()
    report.passport.title = (
        "Очень длинное название проектной инициативы для защиты руководителю " * 20
    )
    report.passport.goal = "Очень длинное описание цели проекта " * 80
    report.concepts[0].advantages = ["Слишком длинное преимущество " * 80]
    report.concepts[0].disadvantages = ["Слишком длинный риск выбранной концепции " * 80]
    report.roadmap[0].milestones[0].title = "Очень длинная контрольная точка дорожной карты " * 30
    report.raci[0].activity = "Очень длинная активность матрицы ответственности " * 30
    report.raci[0].responsible = "Очень длинная ответственная роль " * 20
    report.raci[0].accountable = "Очень длинная accountable роль " * 20

    content = export_project_report_pptx(report)
    xml = _slide_xml_text(content)

    assert content.startswith(b"PK")
    assert _slide_count(content) <= 7
    assert "…" in xml
    _assert_no_technical_dump(xml)


def test_pptx_export_highlights_recommended_concept_prefix_match():
    report = _report()
    report.concepts[0].name = "Концепция C — модификация портала"
    report.recommended_concept.concept_name = "Концепция C"

    content = export_project_report_pptx(report)
    xml = _slide_xml_text(content)

    assert "Концепция C — модификация портала" in xml
    assert "Рекомендуемый вариант" in xml
    assert "Рекомендуем к реализации" in xml
    _assert_no_technical_dump(xml)


def test_pptx_export_deduplicates_slide_need_success_criteria():
    report = _report()
    report.passport.success_criteria = [
        "Достижение охвата целевой аудитории",
        "Получение положительных отзывов о мероприятии",
        "Достижение охвата целевой аудитории",
        "Получение положительных отзывов о мероприятии",
    ]

    content = export_project_report_pptx(report)
    xml = _slide_xml_text(content)

    assert xml.count("Достижение охвата целевой аудитории") == 1
    assert xml.count("Получение положительных отзывов о мероприятии") == 1
    assert "Детальные критерии — в DOCX." in xml
    _assert_no_technical_dump(xml)


async def test_project_planner_pptx_endpoint_returns_existing_run_presentation(
    db_session,
    monkeypatch,
):
    async def fail_if_generation_is_called(*args, **kwargs):  # noqa: ANN002, ANN003, ARG001
        pytest.fail("PPTX endpoint must not generate a new Project Planner report")

    monkeypatch.setattr(project_service, "generate_project_report", fail_if_generation_is_called)
    run_id = await _insert_run(db_session, _report())
    runs_before = await _count_rows(db_session, ProjectPlannerRun)
    artifacts_before = await _count_rows(db_session, ProjectArtifact)
    app, client = _build_test_client(db_session)

    async with client:
        response = await client.get(f"/api/project-planner/runs/{run_id}/pptx")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == PPTX_MEDIA_TYPE
    assert response.headers["content-disposition"].endswith(f'project-planner-run-{run_id}.pptx"')
    assert response.content.startswith(b"PK")
    assert await _count_rows(db_session, ProjectPlannerRun) == runs_before
    assert await _count_rows(db_session, ProjectArtifact) == artifacts_before


async def test_project_planner_pptx_endpoint_missing_run_returns_404(db_session):
    app, client = _build_test_client(db_session)

    async with client:
        response = await client.get("/api/project-planner/runs/999999/pptx")
    app.dependency_overrides.clear()

    assert response.status_code == 404
