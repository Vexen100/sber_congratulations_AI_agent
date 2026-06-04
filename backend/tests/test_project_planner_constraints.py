from __future__ import annotations

import datetime as dt
import json

import pytest

from app.core.config import settings
from app.llm.provider import LLMResponse
from app.project_planner.budget import BUDGET_CONCEPT_COST_ALIGNMENT_WARNING
from app.project_planner.constraint_guardrails import (
    CONCEPT_CONSTRAINT_CORRECTION_WARNING,
    CONCEPT_CONSTRAINT_VALIDATION_WARNING,
    ProjectConstraintProfile,
    apply_concept_constraint_guardrails,
    build_constraint_prompt_context,
    concept_violates_constraints,
    extract_project_constraints,
)
from app.project_planner.generator import generate_project_report
from app.project_planner.mock_generator import build_mock_report
from app.project_planner.prompts import build_user_prompt
from app.project_planner.schemas import ConceptOption, ProjectPlannerInput
from app.project_planner.validators import validate_project_report


def _constraint_payload() -> ProjectPlannerInput:
    return ProjectPlannerInput(
        idea=(
            "Запустить внутренний сервис регистрации инициатив с маршрутизацией заявок "
            "и пилотом в одном направлении"
        ),
        deadline=dt.date.today() + dt.timedelta(days=120),
        budget=2_000_000,
        geography="Челябинская область",
        stakeholders="Product owner, ИТ, ИБ, support/admin, руководители направлений",
        current_resources="Команда бизнес-анализа и тестовый MVP-контур",
        technology_constraints=(
            "Не использовать внешние SaaS, интеграции только через внутренний контур"
        ),
        project_accents="Сделать пилот на одном направлении и подготовить масштабирование",
    )


def _internal_channels_payload() -> ProjectPlannerInput:
    return ProjectPlannerInput(
        idea="Провести внутреннюю коммуникационную кампанию для сотрудников банка",
        deadline=dt.date.today() + dt.timedelta(days=90),
        geography="Свердловская область",
        stakeholders="Команда внутренних коммуникаций и руководители направлений",
        current_resources="Внутренний портал и рассылки",
        technology_constraints="Использовать только согласованные внутренние каналы",
        project_accents="Не выходить в публичные каналы коммуникаций",
    )


def _neutral_payload() -> ProjectPlannerInput:
    return ProjectPlannerInput(
        idea="Подготовить управляемую инициативу для внутреннего согласования",
        deadline=dt.date.today() + dt.timedelta(days=90),
        geography="Свердловская область",
        stakeholders="Бизнес-заказчик и проектная команда",
        current_resources="Базовая команда проекта",
        project_accents="Собрать понятный MVP-план",
    )


def _concept_with_text(**updates: object) -> ConceptOption:
    concept = build_mock_report(_constraint_payload()).concepts[0]
    return concept.model_copy(update=updates)


def _report_json(payload: ProjectPlannerInput) -> dict:
    return build_mock_report(payload).model_dump(mode="json")


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


def _technical_warning_text(warnings: list[str]) -> str:
    return "\n".join(warnings)


def test_constraint_extraction_detects_internal_contour_and_no_external_saas():
    profile = extract_project_constraints(_constraint_payload())

    assert profile.has_constraints
    assert profile.no_external_saas is True
    assert profile.internal_contour_only is True
    assert profile.internal_channels_only is False
    assert profile.matched_constraints == ("no_external_saas", "internal_contour_only")


def test_constraint_extraction_detects_internal_channels_only():
    profile = extract_project_constraints(_internal_channels_payload())

    assert profile.has_constraints
    assert profile.internal_channels_only is True
    assert profile.no_external_saas is False
    assert profile.internal_contour_only is False


def test_constraint_extraction_keeps_neutral_input_unconstrained():
    profile = extract_project_constraints(_neutral_payload())

    assert profile.has_constraints is False
    assert profile.matched_constraints == ()


def test_constraint_extraction_does_not_treat_support_services_as_external_saas():
    payload = _neutral_payload().model_copy(
        update={"technology_constraints": "Без сервисов поддержки"}
    )

    profile = extract_project_constraints(payload)

    assert profile.no_external_saas is False
    assert profile.has_constraints is False


def test_concept_violation_detects_forbidden_external_saas_proposal():
    concept = _concept_with_text(
        name="Использование внешнего решения SaaS",
        key_idea="Запустить регистрацию инициатив через внешнюю SaaS-платформу.",
    )

    assert concept_violates_constraints(
        concept,
        ProjectConstraintProfile(no_external_saas=True),
    )


@pytest.mark.parametrize(
    ("name", "key_idea"),
    [
        (
            "Внешнее SaaS-решение",
            "Запустить регистрацию инициатив через внешнее SaaS-решение.",
        ),
        (
            "Внешнее saas решение",
            "Запустить регистрацию инициатив через внешнее saas решение.",
        ),
        (
            "Внешняя SaaS-платформа",
            "Запустить регистрацию инициатив через внешнюю SaaS-платформу.",
        ),
    ],
)
def test_concept_violation_detects_saas_solution_and_platform_forms(
    name: str,
    key_idea: str,
):
    concept = _concept_with_text(name=name, key_idea=key_idea)

    assert concept_violates_constraints(
        concept,
        ProjectConstraintProfile(no_external_saas=True),
    )


def test_concept_violation_allows_negated_or_unrelated_external_phrases():
    profile = ProjectConstraintProfile(no_external_saas=True)
    compliant = _concept_with_text(
        name="Внутренний сценарий без внешних SaaS",
        key_idea="Концепция не использует внешние сервисы и работает в контуре банка.",
    )
    unrelated = _concept_with_text(
        name="Сценарий с внешними участниками",
        key_idea="Внешние участники могут дать обратную связь, но сервисы не подключаются.",
    )

    assert concept_violates_constraints(compliant, profile) is False
    assert concept_violates_constraints(unrelated, profile) is False


def test_concept_violation_detects_public_external_channels():
    concept = _concept_with_text(
        name="Публичная рекламная кампания",
        key_idea="Продвигать проект через публичные соцсети и наружную рекламу.",
    )

    assert concept_violates_constraints(
        concept,
        ProjectConstraintProfile(internal_channels_only=True),
    )


def test_safe_replacement_itself_does_not_violate_constraints():
    payload = _constraint_payload()
    report = build_mock_report(payload)
    report.concepts[0] = _concept_with_text(
        name="Использование внешнего решения SaaS",
        key_idea="Запустить регистрацию инициатив через внешнюю SaaS-платформу.",
    )

    processed = apply_concept_constraint_guardrails(report, payload)
    profile = extract_project_constraints(payload)

    assert CONCEPT_CONSTRAINT_CORRECTION_WARNING in processed.warnings
    assert not any(concept_violates_constraints(concept, profile) for concept in processed.concepts)


def test_user_prompt_includes_compact_hard_constraint_context_once():
    payload = _constraint_payload()

    context = build_constraint_prompt_context(payload)
    prompt = build_user_prompt(payload)

    assert "Hard constraints context" in context
    assert "do not propose external SaaS" in context
    assert len(context) < 300
    assert payload.technology_constraints not in context
    assert "Hard constraints context" in prompt
    assert prompt.count("Не использовать внешние SaaS") == 1
    assert "forbidden proposal signals" not in prompt.lower()


@pytest.mark.asyncio
async def test_generator_replaces_forbidden_saas_concept_in_successful_llm_path(monkeypatch):
    monkeypatch.setattr(settings, "project_planner_use_mock_llm", False, raising=False)
    monkeypatch.setattr(settings, "gigachat_retry_count", 0, raising=False)
    payload = _constraint_payload()
    raw = _report_json(payload)
    original_name = "Использование внешнего решения SaaS"
    raw["concepts"][1].update(
        {
            "name": original_name,
            "key_idea": "Запустить регистрацию инициатив через внешнюю SaaS-платформу.",
            "scenario_steps": [
                "Выбрать облачный сервис.",
                "Настроить форму регистрации.",
                "Подключить пользователей.",
            ],
            "differences": "Отличается использованием внешнего сервиса.",
            "estimated_cost": 12345,
            "effort_level": "высокая",
        }
    )
    raw["recommended_concept"] = {
        "concept_name": original_name,
        "rationale": "LLM выбрал быстрый внешний SaaS.",
        "risks": ["Нужно проверить ограничения."],
    }
    provider = FakeJsonProvider(raw)

    report, model_name, used_fallback = await generate_project_report(payload, provider=provider)

    profile = extract_project_constraints(payload)
    warnings_text = _technical_warning_text(report.warnings)
    concept_names = {concept.name for concept in report.concepts}
    assert used_fallback is False
    assert model_name == "fake-json"
    assert provider.calls == 1
    assert report.warnings.count(CONCEPT_CONSTRAINT_CORRECTION_WARNING) == 1
    assert original_name not in concept_names
    assert report.recommended_concept.concept_name in concept_names
    assert report.recommended_concept.concept_name != original_name
    assert not any(concept_violates_constraints(concept, profile) for concept in report.concepts)
    assert report.resources.financial_total == sum(
        item.amount for item in report.resources.financial_items
    )
    assert report.warnings.count(BUDGET_CONCEPT_COST_ALIGNMENT_WARNING) == 1
    assert report.concepts[1].estimated_cost == round(report.resources.financial_total * 1.15, -3)
    assert "Traceback" not in warnings_text
    assert "ValidationError" not in warnings_text
    assert "Field required" not in warnings_text


def test_validator_warns_on_remaining_forbidden_concept_only_with_constraints():
    payload = _constraint_payload()
    report = build_mock_report(payload)
    report.concepts[0] = _concept_with_text(
        name="Использование внешнего решения SaaS",
        key_idea="Запустить регистрацию инициатив через внешнюю SaaS-платформу.",
    )

    warnings = validate_project_report(report, payload)
    warnings_without_payload = validate_project_report(report)
    neutral_warnings = validate_project_report(report, _neutral_payload())
    warnings_text = _technical_warning_text(warnings)

    assert warnings.count(CONCEPT_CONSTRAINT_VALIDATION_WARNING) == 1
    assert CONCEPT_CONSTRAINT_VALIDATION_WARNING not in warnings_without_payload
    assert CONCEPT_CONSTRAINT_VALIDATION_WARNING not in neutral_warnings
    assert "Traceback" not in warnings_text
    assert "ValidationError" not in warnings_text
    assert "Field required" not in warnings_text
