from __future__ import annotations

import json
import logging
import re

from pydantic import ValidationError

from app.core.config import settings
from app.llm.provider import LLMProvider, get_project_planner_llm_provider
from app.project_planner.llm_normalizer import normalize_llm_project_report_json
from app.project_planner.mock_generator import build_mock_report
from app.project_planner.prompts import SYSTEM_PROMPT, build_user_prompt
from app.project_planner.schemas import ProjectPlannerInput, ProjectReport
from app.project_planner.validators import validate_project_report


logger = logging.getLogger(__name__)
FALLBACK_VALIDATION_WARNING = (
    "LLM-ответ не соответствовал ожидаемой структуре, использован fallback-генератор. "
    "Содержимое требует проверки."
)


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


def _error_summary(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return f"Pydantic validation failed ({exc.error_count()} errors)"
    return exc.__class__.__name__


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
    attempts = max(1, int(settings.gigachat_retry_count) + 1)
    for attempt in range(attempts):
        try:
            response = await provider.generate_text(messages)
            parsed = _extract_json_object(response.content)
            parsed = normalize_llm_project_report_json(parsed, payload)
            report = ProjectReport.model_validate(parsed)
            report.warnings.extend(validate_project_report(report))
            return report, response.model_name, False
        except (json.JSONDecodeError, ValidationError, ProjectPlannerGenerationError) as exc:
            logger.warning(
                "Project Planner LLM response failed validation on attempt %s/%s: %s",
                attempt + 1,
                attempts,
                _error_summary(exc),
                exc_info=True,
            )
            if attempt < attempts - 1:
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Предыдущий ответ не прошёл проверку структуры "
                            f"({_error_summary(exc)}). Верни полный исправленный JSON ProjectReport "
                            "без markdown. Используй roadmap[].name/start_date/end_date/milestones "
                            "и milestones[].title/due_date/description."
                        ),
                    }
                )
        except Exception as exc:
            logger.warning("Project Planner LLM provider failed; using fallback generator.", exc_info=True)
            break

    report = build_mock_report(
        payload,
        extra_warnings=[FALLBACK_VALIDATION_WARNING],
    )
    return report, "fallback", True
