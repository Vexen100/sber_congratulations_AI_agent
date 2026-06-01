from __future__ import annotations

import datetime as dt
import math

from app.project_planner.budget import budget_warnings, estimate_financial_items
from app.project_planner.catalogs import ROADMAP_PHASE_TEMPLATES, UNIVERSAL_ROLES, normalize_region_name
from app.project_planner.schemas import (
    ConceptOption,
    GanttRow,
    Milestone,
    PresentationSlide,
    ProjectPassport,
    ProjectPlannerInput,
    ProjectReport,
    ProjectRole,
    RaciItem,
    RecommendedConcept,
    ResourcePlan,
    RoadmapPhase,
    SourceInput,
)
from app.project_planner.validators import deadline_warnings, source_assumptions, validate_project_report


def _clean(value: str | None, fallback: str) -> str:
    text = (value or "").strip()
    return text or fallback


def _title_from_idea(idea: str) -> str:
    text = " ".join((idea or "").strip().split())
    if not text:
        return "Проектная инициатива Уральского банка"
    return text[:90].rstrip(" .,;") or "Проектная инициатива Уральского банка"


def _effective_deadline(payload: ProjectPlannerInput, today: dt.date) -> dt.date:
    if payload.deadline is None:
        return today + dt.timedelta(days=90)
    if payload.deadline <= today:
        return today + dt.timedelta(days=45)
    if (payload.deadline - today).days < 30:
        return today + dt.timedelta(days=30)
    return payload.deadline


def _phase_dates(today: dt.date, deadline: dt.date, count: int) -> list[tuple[dt.date, dt.date]]:
    days = max((deadline - today).days, count)
    step = max(math.ceil(days / count), 1)
    dates: list[tuple[dt.date, dt.date]] = []
    start = today
    for idx in range(count):
        end = deadline if idx == count - 1 else min(start + dt.timedelta(days=step - 1), deadline)
        dates.append((start, end))
        start = end + dt.timedelta(days=1)
    return dates


def _build_roadmap(payload: ProjectPlannerInput, today: dt.date) -> list[RoadmapPhase]:
    effective_deadline = _effective_deadline(payload, today)
    phase_dates = _phase_dates(today, effective_deadline, len(ROADMAP_PHASE_TEMPLATES))
    phases: list[RoadmapPhase] = []
    for template, (start, end) in zip(ROADMAP_PHASE_TEMPLATES, phase_dates, strict=True):
        interval_days = max((end - start).days, 1)
        milestones: list[Milestone] = []
        for index, title in enumerate(template["milestones"], start=1):
            due = min(start + dt.timedelta(days=round(interval_days * index / 4)), end)
            milestones.append(
                Milestone(
                    title=title,
                    due_date=due,
                    description="Контрольная точка для управляемого MVP-плана.",
                )
            )
        phases.append(
            RoadmapPhase(
                name=template["name"],
                start_date=start,
                end_date=end,
                milestones=milestones,
            )
        )
    return phases


def _build_gantt(roadmap: list[RoadmapPhase]) -> list[GanttRow]:
    rows: list[GanttRow] = []
    for index, phase in enumerate(roadmap):
        rows.append(
            GanttRow(
                phase=phase.name,
                period=f"{phase.start_date.isoformat()} - {phase.end_date.isoformat()}",
                timeline=("· " * index + "█ " * 2 + "· " * (len(roadmap) - index - 1)).strip(),
            )
        )
    return rows


def _build_team() -> list[ProjectRole]:
    return [ProjectRole(**item) for item in UNIVERSAL_ROLES]


def _build_raci(roadmap: list[RoadmapPhase]) -> list[RaciItem]:
    return [
        RaciItem(
            activity=phase.name,
            responsible="Руководитель проекта",
            accountable="Бизнес-заказчик",
            consulted=["Финансовый аналитик", "Коммуникационный менеджер"],
            informed=["Координатор проекта", "Команда проекта"],
        )
        for phase in roadmap
    ]


def _build_concepts(payload: ProjectPlannerInput, estimated_total: float) -> list[ConceptOption]:
    base_title = _title_from_idea(payload.idea)
    region = normalize_region_name(payload.geography)
    return [
        ConceptOption(
            name="Базовая управляемая концепция",
            key_idea=f"Реализовать «{base_title}» через понятный поэтапный план с минимальным риском.",
            scenario_steps=[
                "Зафиксировать цели и участников.",
                "Подготовить ресурсы и коммуникации.",
                "Провести основной этап проекта.",
                "Собрать обратную связь и защитить результат.",
            ],
            advantages=["Низкий риск", "Понятная управляемость", "Быстрый старт"],
            disadvantages=["Ограниченная креативность", "Меньше нестандартных механик"],
            estimated_cost=round(estimated_total * 0.92, -3),
            effort_level="средняя",
            effort_factors=["типовая команда", "умеренные согласования", "контроль бюджета"],
            differences="Фокус на надёжной реализации и управляемом объёме работ.",
        ),
        ConceptOption(
            name="Расширенная вовлекающая концепция",
            key_idea=f"Сделать проект заметным для аудитории в регионе {region} через коммуникации и участие стейкхолдеров.",
            scenario_steps=[
                "Собрать ожидания ключевых групп.",
                "Запустить серию коммуникаций и вовлекающих активностей.",
                "Провести основной проект с расширенным охватом.",
                "Сформировать публичный итоговый пакет материалов.",
            ],
            advantages=["Высокий охват", "Лучше раскрывает ценность", "Сильнее вовлекает аудиторию"],
            disadvantages=["Выше бюджет", "Больше зависимость от согласований"],
            estimated_cost=round(estimated_total * 1.15, -3),
            effort_level="высокая",
            effort_factors=["широкий охват", "коммуникации", "дополнительные подрядчики"],
            differences="Отличается каналами охвата и более активной работой с целевой аудиторией.",
        ),
        ConceptOption(
            name="Инновационная пилотная концепция",
            key_idea="Собрать MVP-формат с пилотной механикой, которую можно масштабировать после защиты.",
            scenario_steps=[
                "Выбрать пилотный сегмент аудитории.",
                "Собрать быстрый прототип решения.",
                "Проверить гипотезы на ограниченном контуре.",
                "Защитить масштабирование по итогам пилота.",
            ],
            advantages=["Нестандартное решение", "Быстрая проверка гипотез", "Потенциал масштабирования"],
            disadvantages=["Выше неопределённость", "Нужна экспертная поддержка"],
            estimated_cost=round(estimated_total * 1.05, -3),
            effort_level="очень высокая",
            effort_factors=["пилотирование", "IT/методическая поддержка", "экспертная оценка"],
            differences="Отличается пилотной логикой и возможностью масштабирования после проверки.",
        ),
    ]


def build_mock_report(
    payload: ProjectPlannerInput,
    *,
    today: dt.date | None = None,
    extra_warnings: list[str] | None = None,
    extra_assumptions: list[str] | None = None,
) -> ProjectReport:
    today = today or dt.date.today()
    title = _title_from_idea(payload.idea)
    roadmap = _build_roadmap(payload, today)
    financial_items = estimate_financial_items(payload)
    estimated_total = float(sum(item.amount for item in financial_items))
    assumptions = source_assumptions(payload) + list(extra_assumptions or [])
    warnings = (
        deadline_warnings(payload, today=today)
        + budget_warnings(payload, estimated_total)
        + list(extra_warnings or [])
    )
    concepts = _build_concepts(payload, estimated_total)
    report = ProjectReport(
        source_input=SourceInput(
            idea=_clean(payload.idea, "Проектная инициатива требует уточнения."),
            deadline=payload.deadline,
            budget=payload.budget,
            geography=payload.geography,
            stakeholders=payload.stakeholders,
            current_resources=payload.current_resources,
            technology_constraints=payload.technology_constraints,
            project_accents=payload.project_accents,
        ),
        passport=ProjectPassport(
            title=title,
            goal=f"Подготовить и реализовать проект «{title}» в интересах Уральского банка.",
            tasks=[
                "Уточнить цели, ограничения и критерии успеха.",
                "Сформировать дорожную карту и команду проекта.",
                "Оценить ресурсы и риски реализации.",
                "Подготовить концепции для защиты и выбрать рекомендуемый вариант.",
            ],
            target_audience=_clean(payload.stakeholders, "Сотрудники и руководители направлений банка."),
            success_criteria=[
                "Согласован паспорт проекта и дорожная карта.",
                "Ресурсы и роли понятны ответственным участникам.",
                "Выбрана концепция для защиты.",
                "Риски и допущения явно зафиксированы.",
            ],
            relevance_for_ural_bank=(
                "Проект поддерживает управляемое развитие внутренних инициатив Уральского банка, "
                "повышает прозрачность планирования и качество коммуникаций."
            ),
            risks=[
                "Недостаток исходных данных может снизить точность оценок.",
                "Сжатые сроки повышают нагрузку на согласования.",
                "Бюджет требует экспертной проверки перед запуском.",
            ],
            assumptions=assumptions,
        ),
        roadmap=roadmap,
        gantt=_build_gantt(roadmap),
        resources=ResourcePlan(
            financial_items=financial_items,
            financial_total=estimated_total,
            material_resources=[
                "Рабочее пространство или площадка проекта",
                "Оборудование для встреч и презентаций",
                "Средства коммуникации и хранения материалов",
            ],
            information_resources=[
                "Шаблон паспорта проекта",
                "Список стейкхолдеров и контактных лиц",
                "Регламенты согласования и критерии приёмки",
            ],
        ),
        team=_build_team(),
        raci=_build_raci(roadmap),
        concepts=concepts,
        recommended_concept=RecommendedConcept(
            concept_name=concepts[0].name,
            rationale=(
                "Для MVP рекомендуется базовая управляемая концепция: она быстрее запускается, "
                "даёт понятную структуру защиты и снижает риск перерасхода бюджета."
            ),
            risks=["Может потребоваться усилить креативную часть после обратной связи заказчика."],
        ),
        warnings=warnings,
        assumptions=assumptions,
        presentation_outline=[
            PresentationSlide(title="Идея и цель проекта", bullets=[title, "Ожидаемый результат"]),
            PresentationSlide(title="Дорожная карта", bullets=[phase.name for phase in roadmap[:4]]),
            PresentationSlide(title="Ресурсы и команда", bullets=["Смета", "Роли", "RACI"]),
            PresentationSlide(title="Три концепции", bullets=[concept.name for concept in concepts]),
            PresentationSlide(title="Рекомендация", bullets=[concepts[0].name, "Риски и следующие шаги"]),
        ],
        defense_script=(
            f"Проект «{title}» предлагается защитить как управляемую инициативу с понятной целью, "
            "поэтапной дорожной картой и прозрачной сметой. Основной акцент защиты — показать, "
            "какую пользу получает Уральский банк, какие ресурсы нужны и почему выбранная концепция "
            "лучше балансирует сроки, бюджет и управляемость."
        ),
    )
    report.warnings.extend(validate_project_report(report))
    return report
