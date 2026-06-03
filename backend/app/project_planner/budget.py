from __future__ import annotations

from app.project_planner.budget_catalog import BudgetResolution, resolve_budget_items
from app.project_planner.schemas import FinancialItem, ProjectPlannerInput, ProjectReport

BUDGET_LLM_OVERWRITE_WARNING = (
    "Финансовая оценка пересчитана backend demo/reference каталогом; "
    "LLM-значения не использовались как источник цен."
)
PRELIMINARY_BUDGET_WARNING = (
    "Оценка бюджета сформирована по demo/reference каталогу MVP и требует экспертной проверки."
)


def _append_unique(warnings: list[str], warning: str) -> None:
    if warning not in warnings:
        warnings.append(warning)


def estimate_financial_items(payload: ProjectPlannerInput) -> list[FinancialItem]:
    return resolve_budget_items(payload).financial_items


def estimate_total_budget(payload: ProjectPlannerInput) -> float:
    return float(sum(item.amount for item in estimate_financial_items(payload)))


def resolve_budget_for_report(payload: ProjectPlannerInput) -> BudgetResolution:
    return resolve_budget_items(payload)


def budget_warnings(payload: ProjectPlannerInput, estimated_total: float) -> list[str]:
    warnings: list[str] = [PRELIMINARY_BUDGET_WARNING]
    for warning in resolve_budget_items(payload).warnings:
        _append_unique(warnings, warning)
    if payload.budget is not None and payload.budget < estimated_total:
        warnings.append(
            "Указанный бюджет ниже предварительной оценки; рекомендуется сократить объём работ "
            "или согласовать дополнительное финансирование."
        )
    if not payload.budget:
        warnings.append(
            "Бюджет не указан пользователем, поэтому смета рассчитана агентом предварительно."
        )
    return warnings


def apply_backend_budget_resolution(
    report: ProjectReport,
    payload: ProjectPlannerInput,
    *,
    warn_on_overwrite: bool = False,
) -> ProjectReport:
    processed = report.model_copy(deep=True)
    resolution = resolve_budget_items(payload)
    processed.resources.financial_items = resolution.financial_items
    processed.resources.financial_total = float(
        sum(item.amount for item in resolution.financial_items)
    )
    for warning in resolution.warnings:
        _append_unique(processed.warnings, warning)
    if warn_on_overwrite:
        _append_unique(processed.warnings, BUDGET_LLM_OVERWRITE_WARNING)
    return processed
