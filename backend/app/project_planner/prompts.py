from __future__ import annotations

import json

from app.project_planner.schemas import ProjectPlannerInput


SYSTEM_PROMPT = (
    "Ты ИИ-агент проектного планирования для Уральского банка. "
    "Отвечай только валидным JSON без markdown. "
    "JSON должен соответствовать структуре ProjectReport: source_input, passport, roadmap, gantt, "
    "resources, team, raci, concepts, recommended_concept, warnings, assumptions, "
    "presentation_outline, defense_script. Все тексты на русском языке."
)


def build_user_prompt(payload: ProjectPlannerInput) -> str:
    data = payload.model_dump(mode="json", by_alias=True)
    return (
        "Сформируй проектный отчёт MVP. Требования: минимум 4 фазы, 3-6 контрольных "
        "точек на фазу, ровно 3 разные концепции, RACI по фазам, предупреждения и "
        "допущения. Исходные данные:\n"
        f"{json.dumps(data, ensure_ascii=False, indent=2)}"
    )
