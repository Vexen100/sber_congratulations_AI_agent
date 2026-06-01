from __future__ import annotations

from app.project_planner.catalogs import BUDGET_BASE_ITEMS, region_coefficient
from app.project_planner.schemas import FinancialItem, ProjectPlannerInput


def estimate_financial_items(payload: ProjectPlannerInput) -> list[FinancialItem]:
    coefficient = region_coefficient(payload.geography)
    items: list[FinancialItem] = []
    for category, base_amount in BUDGET_BASE_ITEMS.items():
        amount = round(base_amount * coefficient, -3)
        items.append(
            FinancialItem(
                category=category,
                amount=amount,
                comment="Предварительная оценка по тестовому справочнику MVP.",
            )
        )
    return items


def estimate_total_budget(payload: ProjectPlannerInput) -> float:
    return float(sum(item.amount for item in estimate_financial_items(payload)))


def budget_warnings(payload: ProjectPlannerInput, estimated_total: float) -> list[str]:
    warnings: list[str] = [
        "Оценка бюджета сделана по тестовым справочникам MVP и требует экспертной проверки."
    ]
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
