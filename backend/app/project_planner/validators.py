from __future__ import annotations

import datetime as dt

from app.core.config import settings
from app.project_planner.domain_playbooks import (
    HIGH_CONFIDENCE_THRESHOLD,
    contains_controlled_keyword,
    select_playbook,
)
from app.project_planner.schemas import (
    ClarificationQuestion,
    ClarificationResponse,
    ProjectPlannerInput,
    ProjectReport,
)

RECOMMENDED_CONCEPT_MISMATCH_WARNING = "Рекомендованная концепция отсутствует в списке концепций."


def source_assumptions(payload: ProjectPlannerInput) -> list[str]:
    assumptions: list[str] = []
    if len((payload.idea or "").strip()) < 30:
        assumptions.append(
            "Идея проекта описана кратко; детализация будет восстановлена по типовым допущениям."
        )
    if payload.deadline is None:
        assumptions.append("Дедлайн не указан; для MVP принят горизонт планирования 90 дней.")
    if not (payload.geography or "").strip():
        assumptions.append(
            "География не указана; применён базовый региональный коэффициент Свердловской области."
        )
    if not (payload.stakeholders or "").strip():
        assumptions.append(
            "Стейкхолдеры не указаны; предполагаются бизнес-заказчик и проектная команда банка."
        )
    if not (payload.current_resources or "").strip():
        assumptions.append(
            "Текущие ресурсы не указаны; команда и ресурсы подобраны как новый проект."
        )
    if not (payload.technology_constraints or "").strip():
        assumptions.append(
            "Технологические ограничения не указаны; критичных IT-ограничений не предполагается."
        )
    if not (payload.project_accents or "").strip():
        assumptions.append(
            "Акценты проекта не указаны; концепции сформированы без дополнительного контекста."
        )
    return assumptions


def deadline_warnings(payload: ProjectPlannerInput, *, today: dt.date | None = None) -> list[str]:
    today = today or dt.date.today()
    if payload.deadline is None:
        return ["Дедлайн не указан: календарный план построен по типовой длительности MVP."]
    days = (payload.deadline - today).days
    if days < 0:
        return ["Дедлайн находится в прошлом; дорожная карта построена как срочная перепланировка."]
    if days < 30:
        return [
            "Срок выглядит нереалистично коротким; часть работ потребуется выполнять параллельно."
        ]
    return []


def source_data_gaps(payload: ProjectPlannerInput) -> list[str]:
    gaps: list[str] = []
    if len((payload.idea or "").strip()) < 30:
        gaps.append("идея проекта описана короче 30 символов")
    if payload.deadline is None:
        gaps.append("не указан дедлайн")
    if not (payload.geography or "").strip():
        gaps.append("не указана география")
    if not (payload.stakeholders or "").strip():
        gaps.append("не указаны стейкхолдеры")
    if not (payload.project_accents or "").strip():
        gaps.append("не указаны акценты проекта")
    return gaps


def build_clarifications(payload: ProjectPlannerInput) -> ClarificationResponse:
    questions: list[ClarificationQuestion] = []
    if len((payload.idea or "").strip()) < 30:
        questions.append(
            ClarificationQuestion(
                field="idea",
                question="Опишите идею проекта чуть подробнее: цель, аудитория и ожидаемый результат.",
                reason="По ТЗ стартовая идея должна быть достаточно полной для SMART-формулировки.",
            )
        )
    if payload.deadline is None:
        questions.append(
            ClarificationQuestion(
                field="deadline",
                question="К какой дате нужен готовый результат проекта?",
                reason="Дедлайн нужен для дорожной карты и проверки реалистичности сроков.",
            )
        )
    if not (payload.geography or "").strip():
        questions.append(
            ClarificationQuestion(
                field="geography",
                question="В каком регионе Уральского банка планируется проект?",
                reason="География влияет на тестовый региональный коэффициент бюджета.",
            )
        )
    if not (payload.stakeholders or "").strip():
        questions.append(
            ClarificationQuestion(
                field="stakeholders",
                question="Кто ключевые стейкхолдеры и кто принимает результат?",
                reason="Это нужно для команды проекта, RACI и сценария защиты.",
            )
        )
    if not (payload.project_accents or "").strip():
        questions.append(
            ClarificationQuestion(
                field="project_accents",
                question="Есть ли акценты проекта или контекст, который важно учесть при защите?",
                reason="Акценты помогают отличить концепции и не потерять важные ограничения заказчика.",
            )
        )

    default_limit = int(settings.project_planner_default_clarifying_questions)
    max_limit = int(settings.project_planner_max_clarifying_questions)
    remaining = max(default_limit - int(payload.questions_asked_count or 0), 0)
    if payload.questions_asked_count >= max_limit:
        visible_questions: list[ClarificationQuestion] = []
    else:
        visible_questions = questions[: remaining or default_limit]
    can_generate = bool(not visible_questions or payload.questions_asked_count >= default_limit)
    if payload.questions_asked_count >= max_limit:
        can_generate = True

    return ClarificationResponse(
        questions=visible_questions,
        can_generate_with_assumptions=can_generate,
        default_limit=default_limit,
        max_limit=max_limit,
    )


def _gantt_has_content(report: ProjectReport) -> bool:
    return any(
        row.phase.strip() and row.period.strip() and row.timeline.strip() for row in report.gantt
    )


def _normalized(value: str) -> str:
    return " ".join(value.strip().lower().replace("ё", "е").split())


def _report_text(report: ProjectReport) -> str:
    chunks: list[str] = [
        report.passport.title,
        report.passport.goal,
        report.passport.target_audience,
        report.passport.relevance_for_ural_bank,
        *report.passport.tasks,
        *report.passport.success_criteria,
        *report.passport.risks,
        *report.resources.material_resources,
        *report.resources.information_resources,
        report.recommended_concept.concept_name,
        report.recommended_concept.rationale,
        *report.recommended_concept.risks,
        report.defense_script or "",
    ]
    for role in report.team:
        chunks.extend([role.title, role.assignment_comment, *role.competencies])
    for item in report.raci:
        chunks.extend(
            [
                item.activity,
                item.responsible,
                item.accountable,
                *item.consulted,
                *item.informed,
            ]
        )
    for concept in report.concepts:
        chunks.extend(
            [
                concept.name,
                concept.key_idea,
                concept.differences,
                *concept.scenario_steps,
                *concept.advantages,
                *concept.disadvantages,
                *concept.effort_factors,
            ]
        )
    for slide in report.presentation_outline:
        chunks.extend([slide.title, *slide.bullets])
    return "\n".join(chunks)


def _recommended_concept_matches(report: ProjectReport) -> bool:
    recommended = _normalized(report.recommended_concept.concept_name)
    return bool(
        recommended
        and any(_concept_name_matches(recommended, concept.name) for concept in report.concepts)
    )


def _concept_name_matches(normalized_recommended: str, concept_name: str) -> bool:
    normalized_name = _normalized(concept_name)
    if normalized_recommended == normalized_name:
        return True
    if not normalized_name.startswith(normalized_recommended):
        return False
    suffix = normalized_name[len(normalized_recommended) :].lstrip()
    return suffix.startswith(("—", "-", ":", "("))


def _domain_expected_keyword_warning(
    report: ProjectReport,
    payload: ProjectPlannerInput,
) -> str | None:
    playbook, classification = select_playbook(payload)
    if classification.project_type not in {"it_service", "event"}:
        return None
    if classification.confidence < HIGH_CONFIDENCE_THRESHOLD:
        return None
    expected_keywords = playbook.expected_keywords
    if not expected_keywords:
        return None

    text = _report_text(report)
    found = [keyword for keyword in expected_keywords if contains_controlled_keyword(text, keyword)]
    minimum_found = max(2, len(expected_keywords) // 2)
    if len(found) >= minimum_found:
        return None
    missing = [keyword for keyword in expected_keywords if keyword not in found]
    return (
        f"Отчёт для типа проекта «{playbook.display_name}» слабо отражает доменные признаки: "
        f"{', '.join(missing[:6])}."
    )


def validate_project_report(
    report: ProjectReport,
    payload: ProjectPlannerInput | None = None,
    *,
    current_date: dt.date | None = None,
) -> list[str]:
    warnings: list[str] = []
    if payload is not None:
        current_date = current_date or dt.date.today()
    if len(report.roadmap) < 4:
        warnings.append(
            "В дорожной карте меньше 4 фаз; структура была усилена fallback-валидатором."
        )
    for phase in report.roadmap:
        if len(phase.milestones) < 3:
            warnings.append(f"В фазе «{phase.name}» меньше 3 контрольных точек.")
        if len(phase.milestones) > 6:
            warnings.append(f"В фазе «{phase.name}» больше 6 контрольных точек.")
        if phase.start_date > phase.end_date:
            warnings.append(f"В фазе «{phase.name}» дата старта позже даты окончания.")
        if payload and current_date and phase.start_date < current_date:
            warnings.append(f"Фаза «{phase.name}» начинается раньше даты генерации.")
        if payload and payload.deadline and phase.end_date > payload.deadline:
            warnings.append(f"Фаза «{phase.name}» выходит за пользовательский дедлайн.")
        if payload:
            for milestone in phase.milestones:
                if current_date and milestone.due_date < current_date:
                    warnings.append(
                        f"Контрольная точка «{milestone.title}» назначена раньше даты генерации."
                    )
                if payload.deadline and milestone.due_date > payload.deadline:
                    warnings.append(
                        f"Контрольная точка «{milestone.title}» выходит за пользовательский дедлайн."
                    )
    if report.roadmap and not _gantt_has_content(report):
        warnings.append("Gantt-like представление не заполнено.")
    if len(report.concepts) != 3:
        warnings.append("Количество концепций отличается от требуемых трёх.")
    names = [item.name.strip().lower() for item in report.concepts]
    ideas = [item.key_idea.strip().lower() for item in report.concepts]
    if len(set(names)) != len(names) or len(set(ideas)) != len(ideas):
        warnings.append("Концепции выглядят похожими; требуется экспертная проверка уникальности.")
    if not _recommended_concept_matches(report):
        warnings.append(RECOMMENDED_CONCEPT_MISMATCH_WARNING)
    if not report.raci:
        warnings.append("RACI-матрица не заполнена.")
    if payload:
        domain_warning = _domain_expected_keyword_warning(report, payload)
        if domain_warning:
            warnings.append(domain_warning)
    return warnings
