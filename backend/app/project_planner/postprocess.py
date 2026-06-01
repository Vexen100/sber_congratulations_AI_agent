from __future__ import annotations

import datetime as dt

from app.project_planner.schemas import (
    GanttRow,
    Milestone,
    ProjectPlannerInput,
    ProjectReport,
    RoadmapPhase,
)


ROADMAP_DEADLINE_CORRECTION_WARNING = (
    "Дорожная карта была скорректирована, так как исходный LLM-план выходил "
    "за пользовательский дедлайн."
)
ROADMAP_SHORT_DEADLINE_WARNING = (
    "Срок слишком короткий для полноценной дорожной карты; даты сжаты до минимального "
    "демонстрационного плана."
)
ROADMAP_DEADLINE_FALLBACK_WARNING = (
    "LLM-дорожная карта не могла быть безопасно скорректирована под пользовательский дедлайн; "
    "использован fallback-генератор."
)
ROADMAP_START_DATE_CORRECTION_WARNING = (
    "Дорожная карта была скорректирована, так как исходный LLM-план начинался раньше даты генерации."
)
ROADMAP_PAST_DEADLINE_FALLBACK_WARNING = (
    "Пользовательский дедлайн уже прошёл или раньше текущей даты; построен fallback-план с допущениями."
)


def _current_date() -> dt.date:
    return dt.date.today()


def _append_warning(report: ProjectReport, warning: str) -> None:
    if warning not in report.warnings:
        report.warnings.append(warning)


def _needs_deadline_correction(report: ProjectReport, deadline: dt.date) -> bool:
    for phase in report.roadmap:
        if phase.end_date > deadline:
            return True
        if any(milestone.due_date > deadline for milestone in phase.milestones):
            return True
    return False


def _needs_start_date_correction(report: ProjectReport, current_date: dt.date) -> bool:
    for phase in report.roadmap:
        if phase.start_date < current_date:
            return True
        if any(milestone.due_date < current_date for milestone in phase.milestones):
            return True
    return False


def _is_gantt_row_filled(row: GanttRow) -> bool:
    return bool(row.phase.strip() and row.period.strip() and row.timeline.strip())


def is_gantt_valid(rows: list[GanttRow]) -> bool:
    return any(_is_gantt_row_filled(row) for row in rows)


def _phase_bar(index: int, total: int, *, width: int = 8) -> str:
    if total <= 1:
        return "█" * width
    start = min((index * width) // total, width - 1)
    end = min(max(((index + 1) * width) // total, start + 1), width)
    return "░" * start + "█" * (end - start) + "░" * (width - end)


def build_gantt_from_roadmap(roadmap: list[RoadmapPhase]) -> list[GanttRow]:
    total = len(roadmap)
    return [
        GanttRow(
            phase=phase.name,
            period=f"{phase.start_date.strftime('%d.%m.%Y')}–{phase.end_date.strftime('%d.%m.%Y')}",
            timeline=_phase_bar(index, total),
        )
        for index, phase in enumerate(roadmap)
    ]


def _date_at_offset(start: dt.date, end: dt.date, numerator: int, denominator: int) -> dt.date:
    if denominator <= 0:
        return start
    total_days = max((end - start).days, 0)
    offset = round(total_days * numerator / denominator)
    return min(start + dt.timedelta(days=offset), end)


def _compressed_phase_dates(
    start_date: dt.date,
    deadline: dt.date,
    phase_count: int,
) -> list[tuple[dt.date, dt.date]]:
    if phase_count <= 0:
        return []
    dates: list[tuple[dt.date, dt.date]] = []
    for index in range(phase_count):
        phase_start = _date_at_offset(start_date, deadline, index, phase_count)
        phase_end = _date_at_offset(start_date, deadline, index + 1, phase_count)
        if phase_start > phase_end:
            phase_start = phase_end
        dates.append((phase_start, phase_end))
    return dates


def _compressed_milestones(
    milestones: list[Milestone],
    phase_start: dt.date,
    phase_end: dt.date,
) -> list[Milestone]:
    if not milestones:
        return []
    result: list[Milestone] = []
    for index, milestone in enumerate(milestones, start=1):
        due_date = _date_at_offset(phase_start, phase_end, index, len(milestones))
        result.append(milestone.model_copy(update={"due_date": due_date}))
    return result


def enforce_roadmap_deadline(
    report: ProjectReport,
    payload: ProjectPlannerInput,
    *,
    current_date: dt.date | None = None,
) -> tuple[ProjectReport, str | None]:
    if payload.deadline is None or not report.roadmap:
        return report, None

    current_date = current_date or _current_date()
    deadline = payload.deadline
    if current_date > deadline:
        return report, ROADMAP_PAST_DEADLINE_FALLBACK_WARNING

    needs_deadline_correction = _needs_deadline_correction(report, deadline)
    needs_start_date_correction = _needs_start_date_correction(report, current_date)
    if not needs_deadline_correction and not needs_start_date_correction:
        return report, None

    min_existing_start = min(phase.start_date for phase in report.roadmap)
    effective_start = max(min_existing_start, current_date)
    if effective_start > deadline:
        return report, ROADMAP_DEADLINE_FALLBACK_WARNING

    processed = report.model_copy(deep=True)
    phase_dates = _compressed_phase_dates(effective_start, deadline, len(processed.roadmap))
    if not phase_dates:
        return report, ROADMAP_DEADLINE_FALLBACK_WARNING

    compressed_phases: list[RoadmapPhase] = []
    for phase, (phase_start, phase_end) in zip(processed.roadmap, phase_dates, strict=True):
        compressed_phases.append(
            phase.model_copy(
                update={
                    "start_date": phase_start,
                    "end_date": phase_end,
                    "milestones": _compressed_milestones(
                        phase.milestones,
                        phase_start,
                        phase_end,
                    ),
                },
            )
        )
    processed.roadmap = compressed_phases
    processed.gantt = build_gantt_from_roadmap(processed.roadmap)
    if needs_deadline_correction:
        _append_warning(processed, ROADMAP_DEADLINE_CORRECTION_WARNING)
    if needs_start_date_correction:
        _append_warning(processed, ROADMAP_START_DATE_CORRECTION_WARNING)

    available_days = (deadline - effective_start).days + 1
    full_plan_days = max(len(processed.roadmap) * 7, 1)
    if available_days < full_plan_days:
        _append_warning(processed, ROADMAP_SHORT_DEADLINE_WARNING)
    return processed, None


def postprocess_project_report(
    report: ProjectReport,
    payload: ProjectPlannerInput,
    *,
    current_date: dt.date | None = None,
) -> tuple[ProjectReport, str | None]:
    processed, fallback_warning = enforce_roadmap_deadline(
        report.model_copy(deep=True),
        payload,
        current_date=current_date,
    )
    if fallback_warning:
        return processed, fallback_warning
    if processed.roadmap and not is_gantt_valid(processed.gantt):
        processed.gantt = build_gantt_from_roadmap(processed.roadmap)
    return processed, None
