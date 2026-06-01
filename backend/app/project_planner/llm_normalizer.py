from __future__ import annotations

import copy
import datetime as dt
import re
from typing import Any

from pydantic import ValidationError

from app.project_planner.budget import estimate_financial_items
from app.project_planner.schemas import ProjectPlannerInput, ResourcePlan

_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def _is_scalar(value: Any) -> bool:
    return isinstance(value, str | int | float | bool)


def _list_to_string(value: Any) -> Any:
    if not isinstance(value, list):
        return value
    parts: list[str] = []
    for item in value:
        if item is None:
            continue
        if not _is_scalar(item):
            return value
        text = str(item).strip()
        if text:
            parts.append(text)
    return "; ".join(parts)


def _string_to_list(value: Any) -> Any:
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[;\n,]+", value) if part.strip()]
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            if item is None:
                continue
            if not _is_scalar(item):
                return value
            text = str(item).strip()
            if text:
                items.append(text)
        return items
    return value


def _safe_string_list(value: Any) -> list[str] | None:
    normalized = _string_to_list(value)
    if isinstance(normalized, list) and all(isinstance(item, str) for item in normalized):
        return normalized
    return None


def _extract_iso_date(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    for match in _DATE_RE.finditer(value):
        candidate = match.group(0)
        try:
            dt.date.fromisoformat(candidate)
        except ValueError:
            continue
        return candidate
    return None


def _normalize_list_fields(container: Any, fields: tuple[str, ...]) -> None:
    if not isinstance(container, dict):
        return
    for field in fields:
        if field in container:
            container[field] = _string_to_list(container[field])


def _normalize_source_input(data: dict[str, Any]) -> None:
    source = data.get("source_input")
    if not isinstance(source, dict):
        return
    for field in (
        "idea",
        "geography",
        "stakeholders",
        "current_resources",
        "technology_constraints",
        "project_accents",
    ):
        if field in source:
            source[field] = _list_to_string(source[field])


def _normalize_roadmap(data: dict[str, Any]) -> None:
    roadmap = data.get("roadmap")
    if not isinstance(roadmap, list):
        return

    for phase in roadmap:
        if not isinstance(phase, dict):
            continue

        if "name" not in phase and "title" in phase:
            phase["name"] = phase["title"]
        if "milestones" not in phase and "control_points" in phase:
            phase["milestones"] = phase["control_points"]

        milestones = phase.get("milestones")
        due_dates: list[str] = []
        if isinstance(milestones, list):
            for milestone in milestones:
                if not isinstance(milestone, dict):
                    continue
                if "title" not in milestone and "name" in milestone:
                    milestone["title"] = milestone["name"]
                if "due_date" not in milestone:
                    due_date = (
                        _extract_iso_date(milestone.get("title"))
                        or _extract_iso_date(milestone.get("name"))
                        or _extract_iso_date(milestone.get("description"))
                    )
                    if due_date:
                        milestone["due_date"] = due_date
                if "description" not in milestone and isinstance(milestone.get("title"), str):
                    milestone["description"] = milestone["title"]

                due_date_value = milestone.get("due_date")
                if isinstance(due_date_value, str):
                    try:
                        dt.date.fromisoformat(due_date_value)
                    except ValueError:
                        continue
                    due_dates.append(due_date_value)

        if due_dates:
            if "start_date" not in phase:
                phase["start_date"] = min(due_dates)
            if "end_date" not in phase:
                phase["end_date"] = max(due_dates)


def _calculated_resources(
    payload: ProjectPlannerInput, source: dict[str, Any] | None = None
) -> dict[str, Any]:
    financial_items = estimate_financial_items(payload)
    resources = ResourcePlan(
        financial_items=financial_items,
        financial_total=float(sum(item.amount for item in financial_items)),
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
    ).model_dump(mode="json")

    if source:
        material_resources = _safe_string_list(source.get("material_resources"))
        information_resources = _safe_string_list(source.get("information_resources"))
        if material_resources:
            resources["material_resources"] = material_resources
        if information_resources:
            resources["information_resources"] = information_resources
    return resources


def _normalize_resources(data: dict[str, Any], payload: ProjectPlannerInput) -> None:
    resources = data.get("resources")
    if isinstance(resources, dict):
        candidate = copy.deepcopy(resources)
        for field in ("material_resources", "information_resources"):
            if field in candidate:
                candidate[field] = _string_to_list(candidate[field])
        try:
            ResourcePlan.model_validate(candidate)
        except ValidationError:
            data["resources"] = _calculated_resources(payload, candidate)
        else:
            data["resources"] = candidate
    else:
        data["resources"] = _calculated_resources(payload)


def _normalize_passport(data: dict[str, Any]) -> None:
    passport = data.get("passport")
    if not isinstance(passport, dict):
        return
    _normalize_list_fields(passport, ("tasks", "success_criteria", "risks", "assumptions"))


def _normalize_team(data: dict[str, Any]) -> None:
    team = data.get("team")
    if not isinstance(team, list):
        return
    for role in team:
        if isinstance(role, dict) and "competencies" in role:
            role["competencies"] = _string_to_list(role["competencies"])


def _normalize_raci(data: dict[str, Any]) -> None:
    raci = data.get("raci")
    if not isinstance(raci, list):
        return
    for item in raci:
        _normalize_list_fields(item, ("consulted", "informed"))


def _normalize_concepts(data: dict[str, Any]) -> None:
    concepts = data.get("concepts")
    if not isinstance(concepts, list):
        return
    for concept in concepts:
        if not isinstance(concept, dict):
            continue
        _normalize_list_fields(
            concept,
            ("scenario_steps", "advantages", "disadvantages", "effort_factors"),
        )
        if "differences" in concept:
            concept["differences"] = _list_to_string(concept["differences"])


def _normalize_recommended_concept(data: dict[str, Any]) -> None:
    recommended = data.get("recommended_concept")
    _normalize_list_fields(recommended, ("risks",))


def _normalize_presentation_outline(data: dict[str, Any]) -> None:
    outline = data.get("presentation_outline")
    if not isinstance(outline, list):
        return
    for slide in outline:
        _normalize_list_fields(slide, ("bullets",))


def normalize_llm_project_report_json(
    raw: dict[str, Any], payload: ProjectPlannerInput
) -> dict[str, Any]:
    """Repair common LLM JSON shape mistakes without generating missing report sections."""

    data = copy.deepcopy(raw)
    _normalize_source_input(data)
    _normalize_passport(data)
    _normalize_roadmap(data)
    _normalize_resources(data, payload)
    _normalize_team(data)
    _normalize_raci(data)
    _normalize_concepts(data)
    _normalize_recommended_concept(data)
    _normalize_list_fields(data, ("warnings", "assumptions"))
    _normalize_presentation_outline(data)
    return data
