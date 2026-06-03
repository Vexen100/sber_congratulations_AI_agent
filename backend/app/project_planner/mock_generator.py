from __future__ import annotations

import datetime as dt
import math

from app.project_planner.budget import budget_warnings, estimate_financial_items
from app.project_planner.catalogs import normalize_region_name
from app.project_planner.domain_playbooks import DomainPlaybook, select_playbook
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
from app.project_planner.validators import (
    deadline_warnings,
    source_assumptions,
    validate_project_report,
)


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


def _build_roadmap(
    payload: ProjectPlannerInput,
    today: dt.date,
    playbook: DomainPlaybook,
) -> list[RoadmapPhase]:
    effective_deadline = _effective_deadline(payload, today)
    phase_dates = _phase_dates(today, effective_deadline, len(playbook.phases))
    phases: list[RoadmapPhase] = []
    for template, (start, end) in zip(playbook.phases, phase_dates, strict=True):
        interval_days = max((end - start).days, 1)
        milestones: list[Milestone] = []
        for index, title in enumerate(template.milestones, start=1):
            due = min(
                start + dt.timedelta(days=round(interval_days * index / len(template.milestones))),
                end,
            )
            milestones.append(
                Milestone(
                    title=title,
                    due_date=due,
                    description="Контрольная точка для управляемого MVP-плана.",
                )
            )
        phases.append(
            RoadmapPhase(
                name=template.name,
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


def _build_team(playbook: DomainPlaybook) -> list[ProjectRole]:
    return [
        ProjectRole(
            title=role.title,
            count=role.count,
            competencies=list(role.competencies),
            assignment_comment=role.assignment_comment,
        )
        for role in playbook.roles
    ]


def _build_raci(roadmap: list[RoadmapPhase], playbook: DomainPlaybook) -> list[RaciItem]:
    return [
        RaciItem(
            activity=(
                playbook.raci_activities[index]
                if index < len(playbook.raci_activities)
                else phase.name
            ),
            responsible=playbook.raci_defaults.responsible,
            accountable=playbook.raci_defaults.accountable,
            consulted=list(playbook.raci_defaults.consulted),
            informed=list(playbook.raci_defaults.informed),
        )
        for index, phase in enumerate(roadmap)
    ]


def _concept_cost_multiplier(effort_level: str) -> float:
    normalized = " ".join(effort_level.strip().lower().split())
    if normalized == "низкая":
        return 0.90
    if normalized == "высокая" or normalized == "очень высокая":
        return 1.15
    return 1.00


def _build_concepts(
    payload: ProjectPlannerInput,
    estimated_total: float,
    playbook: DomainPlaybook,
) -> list[ConceptOption]:
    base_title = _title_from_idea(payload.idea)
    region = normalize_region_name(payload.geography)
    concepts: list[ConceptOption] = []
    for pattern in playbook.concept_patterns:
        key_idea = pattern.key_idea.replace("инициативу", f"«{base_title}»")
        key_idea = key_idea.replace("аудитории", f"аудитории в регионе {region}")
        concepts.append(
            ConceptOption(
                name=pattern.name,
                key_idea=key_idea,
                scenario_steps=list(pattern.scenario_steps),
                advantages=list(pattern.advantages),
                disadvantages=list(pattern.disadvantages),
                estimated_cost=round(
                    estimated_total * _concept_cost_multiplier(pattern.effort_level),
                    -3,
                ),
                effort_level=pattern.effort_level,
                effort_factors=list(pattern.effort_factors),
                differences=pattern.differences,
            )
        )
    return concepts


def build_mock_report(
    payload: ProjectPlannerInput,
    *,
    today: dt.date | None = None,
    extra_warnings: list[str] | None = None,
    extra_assumptions: list[str] | None = None,
) -> ProjectReport:
    today = today or dt.date.today()
    playbook, _classification = select_playbook(payload)
    title = _title_from_idea(payload.idea)
    roadmap = _build_roadmap(payload, today, playbook)
    financial_items = estimate_financial_items(payload)
    estimated_total = float(sum(item.amount for item in financial_items))
    assumptions = source_assumptions(payload) + list(extra_assumptions or [])
    warnings = (
        deadline_warnings(payload, today=today)
        + budget_warnings(payload, estimated_total)
        + list(extra_warnings or [])
    )
    concepts = _build_concepts(payload, estimated_total, playbook)
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
            target_audience=_clean(
                payload.stakeholders, "Сотрудники и руководители направлений банка."
            ),
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
            risks=list(playbook.risks),
            assumptions=assumptions,
        ),
        roadmap=roadmap,
        gantt=_build_gantt(roadmap),
        resources=ResourcePlan(
            financial_items=financial_items,
            financial_total=estimated_total,
            material_resources=list(playbook.material_resources),
            information_resources=list(playbook.information_resources),
        ),
        team=_build_team(playbook),
        raci=_build_raci(roadmap, playbook),
        concepts=concepts,
        recommended_concept=RecommendedConcept(
            concept_name=concepts[0].name,
            rationale=(
                f"Для MVP рекомендуется «{concepts[0].name}»: она быстрее запускается, "
                "даёт понятную структуру защиты и снижает риск перерасхода бюджета."
            ),
            risks=["Может потребоваться усилить креативную часть после обратной связи заказчика."],
        ),
        warnings=warnings,
        assumptions=assumptions,
        presentation_outline=[
            PresentationSlide(title="Идея и цель проекта", bullets=[title, "Ожидаемый результат"]),
            PresentationSlide(
                title="Дорожная карта", bullets=[phase.name for phase in roadmap[:4]]
            ),
            PresentationSlide(title="Ресурсы и команда", bullets=["Смета", "Роли", "RACI"]),
            PresentationSlide(
                title="Три концепции", bullets=[concept.name for concept in concepts]
            ),
            PresentationSlide(
                title="Рекомендация", bullets=[concepts[0].name, "Риски и следующие шаги"]
            ),
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
