from __future__ import annotations

from app.project_planner.budget_catalog import BudgetResolution, resolve_budget_items
from app.project_planner.schemas import FinancialItem, ProjectPlannerInput, ProjectReport

BUDGET_LLM_OVERWRITE_WARNING = (
    "Финансовая оценка пересчитана backend demo/reference каталогом; "
    "LLM-значения не использовались как источник цен."
)
BUDGET_CONCEPT_COST_ALIGNMENT_WARNING = (
    "Оценки стоимости концепций синхронизированы с backend demo/reference сметой; "
    "LLM-значения не использовались как источник цен."
)
PRELIMINARY_BUDGET_WARNING = (
    "Оценка бюджета сформирована по demo/reference каталогу MVP и требует экспертной проверки."
)

_EFFORT_COST_MULTIPLIERS: dict[str, float] = {
    "низкая": 0.90,
    "средняя": 1.00,
    "высокая": 1.15,
    "очень высокая": 1.15,
}
_POSITIONAL_COST_MULTIPLIERS: tuple[float, ...] = (1.00, 1.15, 0.90)


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


def _concept_cost_multiplier(effort_level: object, index: int) -> float:
    normalized = " ".join(str(effort_level or "").strip().lower().split())
    if normalized in _EFFORT_COST_MULTIPLIERS:
        return _EFFORT_COST_MULTIPLIERS[normalized]
    if index < len(_POSITIONAL_COST_MULTIPLIERS):
        return _POSITIONAL_COST_MULTIPLIERS[index]
    return 1.00


def _align_concept_costs(report: ProjectReport) -> None:
    base_total = float(report.resources.financial_total or 0)
    for index, concept in enumerate(report.concepts):
        multiplier = _concept_cost_multiplier(concept.effort_level, index)
        concept.estimated_cost = round(base_total * multiplier, -3)


def apply_backend_budget_resolution(
    report: ProjectReport,
    payload: ProjectPlannerInput,
    *,
    warn_on_overwrite: bool = False,
    align_concept_costs: bool = False,
) -> ProjectReport:
    processed = report.model_copy(deep=True)
    resolution = resolve_budget_items(payload)
    processed.resources.financial_items = resolution.financial_items
    processed.resources.financial_total = float(
        sum(item.amount for item in resolution.financial_items)
    )
    for warning in resolution.warnings:
        _append_unique(processed.warnings, warning)
    if align_concept_costs:
        _align_concept_costs(processed)
        _append_unique(processed.warnings, BUDGET_CONCEPT_COST_ALIGNMENT_WARNING)
    if warn_on_overwrite:
        _append_unique(processed.warnings, BUDGET_LLM_OVERWRITE_WARNING)
    return processed
