from __future__ import annotations

import json
import re

from pydantic import ValidationError

from app.core.config import settings
from app.llm.provider import LLMProvider, get_project_planner_llm_provider
from app.project_planner.mock_generator import build_mock_report
from app.project_planner.prompts import SYSTEM_PROMPT, build_user_prompt
from app.project_planner.schemas import ProjectPlannerInput, ProjectReport
from app.project_planner.validators import validate_project_report


class ProjectPlannerGenerationError(RuntimeError):
    pass


def _extract_json_object(content: str) -> dict:
    text = content.strip()
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ProjectPlannerGenerationError("LLM returned JSON, but top-level value is not an object")
    return parsed


async def generate_project_report(
    payload: ProjectPlannerInput,
    *,
    provider: LLMProvider | None = None,
) -> tuple[ProjectReport, str, bool]:
    if settings.project_planner_use_mock_llm:
        return build_mock_report(payload), "mock", True

    provider = provider if provider is not None else get_project_planner_llm_provider()
    if provider is None:
        report = build_mock_report(
            payload,
            extra_warnings=["GigaChat не настроен; использован mock/fallback генератор."],
        )
        return report, "fallback", True

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(payload)},
    ]
    last_error: Exception | None = None
    attempts = max(1, int(settings.gigachat_retry_count) + 1)
    for attempt in range(attempts):
        try:
            response = await provider.generate_text(messages)
            parsed = _extract_json_object(response.content)
            report = ProjectReport.model_validate(parsed)
            report.warnings.extend(validate_project_report(report))
            return report, response.model_name, False
        except (json.JSONDecodeError, ValidationError, ProjectPlannerGenerationError) as exc:
            last_error = exc
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Предыдущий ответ не прошёл JSON/Pydantic-валидацию. "
                        f"Попытка {attempt + 1}: {exc}. Верни только исправленный JSON."
                    ),
                }
            )
        except Exception as exc:
            last_error = exc
            break

    report = build_mock_report(
        payload,
        extra_warnings=[
            "LLM-генерация не прошла валидацию; использован fallback-генератор.",
            f"Техническая причина fallback: {last_error}",
        ],
    )
    return report, "fallback", True
