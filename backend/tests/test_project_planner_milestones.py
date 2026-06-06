from __future__ import annotations

import datetime as dt
import json

import pytest

from app.core.config import settings
from app.llm.provider import LLMResponse
from app.project_planner.generator import generate_project_report
from app.project_planner.milestone_guardrails import (
    MILESTONE_DENSITY_CORRECTION_WARNING,
    ensure_minimum_milestone_density,
)
from app.project_planner.mock_generator import build_mock_report
from app.project_planner.schemas import Milestone, ProjectPlannerInput, ProjectReport


def _event_payload() -> ProjectPlannerInput:
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


def _report() -> ProjectReport:
    return build_mock_report(_event_payload())


def _phase_bounds_assert(report: ProjectReport) -> None:
    for phase in report.roadmap:
        for milestone in phase.milestones:
            assert phase.start_date <= milestone.due_date <= phase.end_date


class FakeJsonProvider:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls = 0

    async def generate_text(self, messages: list[dict], **kwargs) -> LLMResponse:  # noqa: ARG002
        self.calls += 1
        return LLMResponse(
            content=json.dumps(self.payload, ensure_ascii=False),
            model_name="fake-json",
        )


def test_milestone_density_adds_minimum_milestones_and_preserves_existing():
    report = _report()
    phase = report.roadmap[0]
    existing = phase.milestones[0].model_copy(deep=True)
    report.roadmap[0] = phase.model_copy(update={"milestones": [existing]})

    processed = ensure_minimum_milestone_density(report)

    processed_phase = processed.roadmap[0]
    assert len(processed_phase.milestones) >= 3
    assert existing.model_dump() in [
        milestone.model_dump() for milestone in processed_phase.milestones
    ]
    assert processed.warnings.count(MILESTONE_DENSITY_CORRECTION_WARNING) == 1
    _phase_bounds_assert(processed)


def test_milestone_density_uses_event_aware_titles_for_festival_phase():
    report = _report()
    phase = report.roadmap[0].model_copy(
        update={
            "name": "Проведение фестиваля",
            "milestones": [],
        }
    )
    report.roadmap[0] = phase

    processed = ensure_minimum_milestone_density(report)

    titles = {milestone.title for milestone in processed.roadmap[0].milestones}
    assert "Проверка готовности площадки и команды" in titles
    assert "Контроль проведения ключевой программы" in titles
    assert "Фиксация итогов и обратной связи" in titles
    _phase_bounds_assert(processed)


def test_milestone_density_leaves_complete_roadmap_unchanged_without_warning():
    report = _report()
    original = report.model_dump(mode="json")

    processed = ensure_minimum_milestone_density(report)

    assert processed.model_dump(mode="json") == original
    assert MILESTONE_DENSITY_CORRECTION_WARNING not in processed.warnings


def test_milestone_density_skips_invalid_phase_window_without_warning():
    report = _report()
    phase = report.roadmap[0]
    invalid_phase = phase.model_copy(
        update={
            "start_date": dt.date(2026, 9, 10),
            "end_date": dt.date(2026, 9, 1),
            "milestones": [phase.milestones[0]],
        }
    )
    report.roadmap = [invalid_phase]

    processed = ensure_minimum_milestone_density(report)

    assert processed.roadmap[0].model_dump() == invalid_phase.model_dump()
    assert MILESTONE_DENSITY_CORRECTION_WARNING not in processed.warnings


def test_milestone_density_suffixes_duplicate_generated_titles():
    report = _report()
    phase = report.roadmap[0]
    duplicate_existing = Milestone(
        title="Проверка готовности площадки и команды",
        due_date=phase.start_date,
        description="Существующая контрольная точка.",
    )
    report.roadmap[0] = phase.model_copy(
        update={"name": "Проведение фестиваля", "milestones": [duplicate_existing]}
    )

    processed = ensure_minimum_milestone_density(report)

    titles = [milestone.title for milestone in processed.roadmap[0].milestones]
    normalized_titles = {title.strip().lower().replace("ё", "е") for title in titles}
    assert len(titles) == len(normalized_titles)
    assert "Проверка готовности площадки и команды — 2" in titles


@pytest.mark.asyncio
async def test_generator_adds_event_milestones_before_validation(monkeypatch):
    monkeypatch.setattr(settings, "project_planner_use_mock_llm", False, raising=False)
    monkeypatch.setattr(settings, "gigachat_retry_count", 0, raising=False)
    payload = _event_payload()
    raw = build_mock_report(payload).model_dump(mode="json")
    raw["roadmap"][0]["name"] = "Проведение фестиваля"
    raw["roadmap"][0]["milestones"] = raw["roadmap"][0]["milestones"][:1]
    provider = FakeJsonProvider(raw)

    report, model_name, used_fallback = await generate_project_report(payload, provider=provider)

    warnings_text = "\n".join(report.warnings)
    festival_phase = next(phase for phase in report.roadmap if phase.name == "Проведение фестиваля")
    assert used_fallback is False
    assert model_name == "fake-json"
    assert provider.calls == 1
    assert len(festival_phase.milestones) >= 3
    assert report.warnings.count(MILESTONE_DENSITY_CORRECTION_WARNING) == 1
    assert "меньше 3 контрольных точек" not in warnings_text
    assert "Traceback" not in warnings_text
    assert "ValidationError" not in warnings_text
    assert "Field required" not in warnings_text
