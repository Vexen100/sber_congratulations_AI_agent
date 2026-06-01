from __future__ import annotations

import json

from app.project_planner.schemas import ProjectPlannerInput

PROJECT_REPORT_JSON_SKELETON = {
    "source_input": {
        "idea": "string",
        "deadline": "2026-09-30",
        "budget": 100000,
        "geography": "string",
        "stakeholders": "string",
        "current_resources": "string",
        "technology_constraints": "string",
        "project_accents": "string",
    },
    "passport": {
        "title": "string",
        "goal": "string",
        "tasks": ["string"],
        "target_audience": "string",
        "success_criteria": ["string"],
        "relevance_for_ural_bank": "string",
        "risks": ["string"],
        "assumptions": ["string"],
    },
    "roadmap": [
        {
            "name": "string",
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "milestones": [
                {
                    "title": "string",
                    "due_date": "2026-09-15",
                    "description": "string",
                }
            ],
        }
    ],
    "gantt": [
        {
            "phase": "string",
            "period": "2026-09-01 - 2026-09-30",
            "timeline": "string",
        }
    ],
    "resources": {
        "financial_items": [
            {
                "category": "string",
                "amount": 100000,
                "comment": "string",
            }
        ],
        "financial_total": 100000,
        "material_resources": ["string"],
        "information_resources": ["string"],
    },
    "team": [
        {
            "title": "string",
            "count": 1,
            "competencies": ["string"],
            "assignment_comment": "string",
        }
    ],
    "raci": [
        {
            "activity": "string",
            "responsible": "string",
            "accountable": "string",
            "consulted": ["string"],
            "informed": ["string"],
        }
    ],
    "concepts": [
        {
            "name": "string",
            "key_idea": "string",
            "scenario_steps": ["string"],
            "advantages": ["string"],
            "disadvantages": ["string"],
            "estimated_cost": 100000,
            "effort_level": "средняя",
            "effort_factors": ["string"],
            "differences": "string",
        }
    ],
    "recommended_concept": {
        "concept_name": "string",
        "rationale": "string",
        "risks": ["string"],
    },
    "warnings": ["string"],
    "assumptions": ["string"],
    "presentation_outline": [
        {
            "title": "string",
            "bullets": ["string"],
        }
    ],
    "defense_script": "string",
}

PROJECT_REPORT_JSON_SKELETON_TEXT = json.dumps(
    PROJECT_REPORT_JSON_SKELETON,
    ensure_ascii=False,
    indent=2,
)

SYSTEM_PROMPT = (
    "Ты ИИ-агент проектного планирования для Уральского банка. "
    "Отвечай только валидным JSON без markdown, пояснений и code fences. "
    "Верни только JSON без комментариев вне JSON. Все ключи обязательны; если данных "
    "не хватает, всё равно верни обязательный ключ со значением правильного типа. "
    "JSON должен соответствовать структуре ProjectReport: source_input, passport, roadmap, gantt, "
    "resources, team, raci, concepts, recommended_concept, warnings, assumptions, "
    "presentation_outline, defense_script. "
    "Запрещены сокращённые формы: passport не может быть только {name, acronym}; "
    "team не может быть list[str]; concepts не может быть list[str]; "
    "raci не может быть dict по phase names; presentation_outline не может быть list[str]; "
    "defense_script должен быть string, не array. "
    "Для roadmap используй только поля name, start_date, end_date, milestones; "
    "не используй title или control_points для фаз. "
    "Для milestones используй только title, due_date, description. "
    "Все даты должны быть строками YYYY-MM-DD. "
    "Roadmap and milestone dates must not be later than the user deadline; "
    "final phase must end on or before deadline; if deadline is too short, keep dates "
    "within deadline and add warning/assumption. "
    "Поля-списки возвращай JSON arrays, строковые поля возвращай strings. "
    "Все тексты на русском языке. "
    "Полный JSON skeleton текущей ProjectReport schema:\n"
    f"{PROJECT_REPORT_JSON_SKELETON_TEXT}"
)


def build_user_prompt(payload: ProjectPlannerInput) -> str:
    data = payload.model_dump(mode="json", by_alias=True)
    return (
        "Сформируй проектный отчёт MVP. Требования: минимум 4 фазы, 3-6 контрольных "
        "точек на фазу, ровно 3 разные концепции, RACI по фазам, предупреждения и "
        "допущения. Исходные данные:\n"
        f"{json.dumps(data, ensure_ascii=False, indent=2)}"
    )
