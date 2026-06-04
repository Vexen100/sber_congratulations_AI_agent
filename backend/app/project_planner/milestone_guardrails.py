from __future__ import annotations

import datetime as dt

from app.project_planner.schemas import Milestone, ProjectReport, RoadmapPhase

MILESTONE_DENSITY_CORRECTION_WARNING = (
    "Дорожная карта была дополнена контрольными точками для равномерности плана."
)

_GENERIC_MILESTONES = (
    (
        "Промежуточная проверка: {phase_name}",
        "Проверить текущий статус работ и зафиксировать открытые вопросы.",
    ),
    (
        "Контроль готовности: {phase_name}",
        "Убедиться, что ключевые результаты фазы готовы к следующему шагу.",
    ),
    (
        "Фиксация результата: {phase_name}",
        "Зафиксировать результат фазы и решения для дальнейшего планирования.",
    ),
)
_EVENT_MILESTONES = (
    (
        "Проверка готовности площадки и команды",
        "Проверить готовность площадки, команды и ключевых организационных элементов.",
    ),
    (
        "Контроль проведения ключевой программы",
        "Убедиться, что ключевая программа проходит по согласованному сценарию.",
    ),
    (
        "Фиксация итогов и обратной связи",
        "Зафиксировать итоги этапа, обратную связь и первичные выводы.",
    ),
)
_REGISTRATION_MILESTONES = (
    (
        "Проверка формы и каналов регистрации",
        "Проверить форму, каналы регистрации и понятность маршрута для участников.",
    ),
    (
        "Контроль набора участников",
        "Сверить динамику регистрации с планом и выявить точки риска.",
    ),
    (
        "Закрытие регистрации и сверка списков",
        "Закрыть регистрацию и сверить итоговые списки участников.",
    ),
)
_PILOT_MILESTONES = (
    (
        "Запуск пилотной проверки",
        "Запустить пилотный сценарий на ограниченной группе пользователей.",
    ),
    (
        "Сбор обратной связи пилота",
        "Собрать обратную связь и зафиксировать основные замечания.",
    ),
    (
        "Фиксация доработок перед запуском",
        "Определить необходимые доработки перед основным запуском.",
    ),
)
_DEVELOPMENT_MILESTONES = (
    (
        "Проверка готовности основного функционала",
        "Проверить готовность ключевого функционала к демонстрации и тестированию.",
    ),
    (
        "Контроль интеграции и ролей доступа",
        "Проверить интеграционные зависимости и базовые роли доступа.",
    ),
    (
        "Фиксация результата технической проверки",
        "Зафиксировать результат технической проверки и список доработок.",
    ),
)


def _normalized(value: str) -> str:
    return " ".join(value.strip().lower().replace("ё", "е").split())


def _milestone_templates_for_phase(phase_name: str) -> tuple[tuple[str, str], ...]:
    normalized = _normalized(phase_name)
    if "регистрац" in normalized:
        return _REGISTRATION_MILESTONES
    if any(token in normalized for token in ("проведени", "фестивал", "мероприяти")):
        return _EVENT_MILESTONES
    if any(token in normalized for token in ("пилот", "тест")):
        return _PILOT_MILESTONES
    if any(token in normalized for token in ("разработ", "интеграц")):
        return _DEVELOPMENT_MILESTONES
    return _GENERIC_MILESTONES


def _date_at_offset(start: dt.date, end: dt.date, numerator: int, denominator: int) -> dt.date:
    if denominator <= 0:
        return start
    total_days = max((end - start).days, 0)
    offset = round(total_days * numerator / denominator)
    return min(max(start + dt.timedelta(days=offset), start), end)


def _unique_title(title: str, existing_titles: set[str]) -> str:
    normalized = _normalized(title)
    if normalized not in existing_titles:
        existing_titles.add(normalized)
        return title

    index = 2
    while True:
        candidate = f"{title} — {index}"
        normalized_candidate = _normalized(candidate)
        if normalized_candidate not in existing_titles:
            existing_titles.add(normalized_candidate)
            return candidate
        index += 1


def _render_template_title(template: str, phase_name: str) -> str:
    return template.format(phase_name=phase_name)


def _build_missing_milestones(
    phase: RoadmapPhase,
    *,
    missing_count: int,
) -> list[Milestone]:
    existing_titles = {_normalized(milestone.title) for milestone in phase.milestones}
    templates = _milestone_templates_for_phase(phase.name)
    result: list[Milestone] = []
    for index in range(missing_count):
        title_template, description = templates[index % len(templates)]
        title = _unique_title(
            _render_template_title(title_template, phase.name),
            existing_titles,
        )
        due_date = _date_at_offset(
            phase.start_date,
            phase.end_date,
            index + 1,
            missing_count + 1,
        )
        result.append(Milestone(title=title, due_date=due_date, description=description))
    return result


def _phase_with_minimum_milestones(
    phase: RoadmapPhase,
    *,
    min_milestones_per_phase: int,
) -> tuple[RoadmapPhase, bool]:
    if len(phase.milestones) >= min_milestones_per_phase:
        return phase, False
    if phase.start_date > phase.end_date:
        return phase, False

    missing_count = min_milestones_per_phase - len(phase.milestones)
    generated = _build_missing_milestones(phase, missing_count=missing_count)
    if not generated:
        return phase, False
    milestones = sorted(
        [*phase.milestones, *generated],
        key=lambda milestone: milestone.due_date,
    )
    return phase.model_copy(update={"milestones": milestones}), True


def _append_warning(report: ProjectReport, warning: str) -> None:
    if warning not in report.warnings:
        report.warnings.append(warning)


def ensure_minimum_milestone_density(
    report: ProjectReport,
    *,
    min_milestones_per_phase: int = 3,
) -> ProjectReport:
    if min_milestones_per_phase <= 0 or not report.roadmap:
        return report

    processed = report.model_copy(deep=True)
    changed = False
    roadmap: list[RoadmapPhase] = []
    for phase in processed.roadmap:
        updated_phase, phase_changed = _phase_with_minimum_milestones(
            phase,
            min_milestones_per_phase=min_milestones_per_phase,
        )
        roadmap.append(updated_phase)
        changed = changed or phase_changed

    if not changed:
        return processed
    processed.roadmap = roadmap
    _append_warning(processed, MILESTONE_DENSITY_CORRECTION_WARNING)
    return processed
