from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass
from importlib import resources
from typing import Any, Mapping

from app.project_planner.catalogs import (
    BUDGET_BASE_ITEMS,
    REGION_COEFFICIENTS,
    normalize_region_name,
    region_coefficient,
)
from app.project_planner.schemas import FinancialItem, ProjectPlannerInput

logger = logging.getLogger(__name__)

CATALOG_RESOURCE_PACKAGE = "app.project_planner.resources"
CATALOG_RESOURCE_NAME = "budget_catalog_v1.json"
VALID_CURRENCIES = {"RUB"}
VALID_CONFIDENCE = {"test", "low", "medium", "high"}
STANDARD_BUDGET_CATEGORY_KEYS: tuple[str, ...] = (
    "project_management",
    "contractors_expertise",
    "marketing_communications",
    "technical_support",
    "risk_reserve",
)
OTHER_CATEGORY_KEY = "other"
CATALOG_EMERGENCY_FALLBACK_WARNING = (
    "Demo/reference каталог бюджета недоступен или не прошёл проверку; "
    "использована аварийная тестовая оценка."
)


class BudgetCatalogError(ValueError):
    pass


@dataclass(frozen=True)
class BudgetCatalogItem:
    category_key: str
    category_name: str
    aliases: tuple[str, ...]
    item_name: str
    region: str
    unit: str
    avg_price: float
    currency: str
    source_name: str
    source_date: str
    confidence: str
    comment: str
    min_price: float | None = None
    max_price: float | None = None


@dataclass(frozen=True)
class BudgetCatalog:
    catalog_name: str
    catalog_version: str
    default_region: str
    currency: str
    source_name: str
    source_date: str
    items: tuple[BudgetCatalogItem, ...]


@dataclass(frozen=True)
class BudgetResolution:
    financial_items: list[FinancialItem]
    warnings: list[str]
    used_emergency_fallback: bool = False


def _clean_text(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise BudgetCatalogError(f"{field_name} must be a string")
    text = " ".join(value.strip().split())
    if not text:
        raise BudgetCatalogError(f"{field_name} must not be empty")
    return text


def _normalized(value: str) -> str:
    return " ".join(value.strip().lower().replace("ё", "е").split())


def _parse_source_date(value: Any, *, field_name: str) -> str:
    text = _clean_text(value, field_name=field_name)
    try:
        return dt.date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise BudgetCatalogError(f"{field_name} must be YYYY-MM-DD") from exc


def _parse_price(value: Any, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise BudgetCatalogError(f"{field_name} must be a number")
    price = float(value)
    if price < 0:
        raise BudgetCatalogError(f"{field_name} must be non-negative")
    return price


def _parse_aliases(value: Any, *, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise BudgetCatalogError(f"{field_name} must be a list")
    aliases: list[str] = []
    for index, item in enumerate(value):
        aliases.append(_clean_text(item, field_name=f"{field_name}[{index}]"))
    return tuple(aliases)


def _optional_price(raw: Mapping[str, Any], key: str) -> float | None:
    if key not in raw or raw[key] is None:
        return None
    return _parse_price(raw[key], field_name=key)


def _parse_item(raw: Any, *, index: int) -> BudgetCatalogItem:
    if not isinstance(raw, Mapping):
        raise BudgetCatalogError(f"items[{index}] must be an object")
    currency = _clean_text(raw.get("currency"), field_name=f"items[{index}].currency")
    if currency not in VALID_CURRENCIES:
        raise BudgetCatalogError(f"items[{index}].currency is not supported")
    confidence = _clean_text(raw.get("confidence"), field_name=f"items[{index}].confidence")
    if confidence not in VALID_CONFIDENCE:
        raise BudgetCatalogError(f"items[{index}].confidence is not supported")

    avg_price = _parse_price(raw.get("avg_price"), field_name=f"items[{index}].avg_price")
    min_price = _optional_price(raw, "min_price")
    max_price = _optional_price(raw, "max_price")
    if min_price is not None and min_price > avg_price:
        raise BudgetCatalogError(f"items[{index}].min_price must be <= avg_price")
    if max_price is not None and avg_price > max_price:
        raise BudgetCatalogError(f"items[{index}].avg_price must be <= max_price")
    if min_price is not None and max_price is not None and min_price > max_price:
        raise BudgetCatalogError(f"items[{index}].min_price must be <= max_price")

    return BudgetCatalogItem(
        category_key=_clean_text(
            raw.get("category_key"), field_name=f"items[{index}].category_key"
        ),
        category_name=_clean_text(
            raw.get("category_name"), field_name=f"items[{index}].category_name"
        ),
        aliases=_parse_aliases(raw.get("aliases"), field_name=f"items[{index}].aliases"),
        item_name=_clean_text(raw.get("item_name"), field_name=f"items[{index}].item_name"),
        region=_clean_text(raw.get("region"), field_name=f"items[{index}].region"),
        unit=_clean_text(raw.get("unit"), field_name=f"items[{index}].unit"),
        avg_price=avg_price,
        currency=currency,
        source_name=_clean_text(raw.get("source_name"), field_name=f"items[{index}].source_name"),
        source_date=_parse_source_date(
            raw.get("source_date"), field_name=f"items[{index}].source_date"
        ),
        confidence=confidence,
        comment=_clean_text(raw.get("comment"), field_name=f"items[{index}].comment"),
        min_price=min_price,
        max_price=max_price,
    )


def parse_budget_catalog(data: Mapping[str, Any]) -> BudgetCatalog:
    currency = _clean_text(data.get("currency"), field_name="currency")
    if currency not in VALID_CURRENCIES:
        raise BudgetCatalogError("currency is not supported")
    raw_items = data.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise BudgetCatalogError("items must be a non-empty list")

    catalog = BudgetCatalog(
        catalog_name=_clean_text(data.get("catalog_name"), field_name="catalog_name"),
        catalog_version=_clean_text(data.get("catalog_version"), field_name="catalog_version"),
        default_region=normalize_region_name(
            _clean_text(data.get("default_region"), field_name="default_region")
        ),
        currency=currency,
        source_name=_clean_text(data.get("source_name"), field_name="source_name"),
        source_date=_parse_source_date(data.get("source_date"), field_name="source_date"),
        items=tuple(_parse_item(item, index=index) for index, item in enumerate(raw_items)),
    )
    category_keys = {item.category_key for item in catalog.items}
    required_keys = set(STANDARD_BUDGET_CATEGORY_KEYS) | {OTHER_CATEGORY_KEY}
    missing = sorted(required_keys - category_keys)
    if missing:
        raise BudgetCatalogError(f"catalog is missing categories: {', '.join(missing)}")
    default_row_missing = sorted(
        category_key
        for category_key in required_keys
        if not any(
            item.category_key == category_key
            and (
                normalize_region_name(item.region) == catalog.default_region
                or _normalized(item.region) == "default"
            )
            for item in catalog.items
        )
    )
    if default_row_missing:
        raise BudgetCatalogError(
            "catalog is missing default/default_region rows for categories: "
            f"{', '.join(default_row_missing)}"
        )
    return catalog


def load_builtin_budget_catalog() -> BudgetCatalog:
    raw_text = (
        resources.files(CATALOG_RESOURCE_PACKAGE)
        .joinpath(CATALOG_RESOURCE_NAME)
        .read_text(encoding="utf-8")
    )
    data = json.loads(raw_text)
    if not isinstance(data, Mapping):
        raise BudgetCatalogError("catalog root must be an object")
    return parse_budget_catalog(data)


def _known_region_names() -> set[str]:
    return {item.name for item in REGION_COEFFICIENTS}


def _append_unique(warnings: list[str], warning: str) -> None:
    if warning not in warnings:
        warnings.append(warning)


def _category_matches(item: BudgetCatalogItem, text: str) -> bool:
    values = (item.category_key, item.category_name, item.item_name, *item.aliases)
    return any(_normalized(value) == text for value in values)


def resolve_category_key(
    category: str,
    catalog: BudgetCatalog | None = None,
) -> tuple[str, list[str]]:
    catalog = catalog or load_builtin_budget_catalog()
    text = _normalized(category)
    for item in catalog.items:
        if _category_matches(item, text):
            return item.category_key, []
    return OTHER_CATEGORY_KEY, [
        f"Категория бюджета «{category}» не найдена в demo/reference каталоге; "
        "использована категория «Прочие расходы»."
    ]


def _find_item(
    catalog: BudgetCatalog,
    *,
    category_key: str,
    region: str,
) -> BudgetCatalogItem | None:
    for item in catalog.items:
        if item.category_key == category_key and normalize_region_name(item.region) == region:
            return item
    return None


def _find_default_item(
    catalog: BudgetCatalog,
    *,
    category_key: str,
) -> tuple[BudgetCatalogItem | None, str]:
    item = _find_item(catalog, category_key=category_key, region=catalog.default_region)
    if item is not None:
        return item, catalog.default_region
    for item in catalog.items:
        if item.category_key == category_key and _normalized(item.region) == "default":
            return item, catalog.default_region
    return None, catalog.default_region


def _provenance_comment(
    catalog: BudgetCatalog,
    item: BudgetCatalogItem,
    *,
    region: str,
) -> str:
    return (
        f"Источник: {item.source_name}; каталог: {catalog.catalog_name} "
        f"{catalog.catalog_version}; дата: {item.source_date}; регион: {region}; "
        f"confidence: {item.confidence}."
    )


def resolve_budget_item(
    category: str,
    payload: ProjectPlannerInput,
    catalog: BudgetCatalog | None = None,
) -> tuple[FinancialItem, list[str]]:
    catalog = catalog or load_builtin_budget_catalog()
    warnings: list[str] = []
    category_key, category_warnings = resolve_category_key(category, catalog)
    warnings.extend(category_warnings)

    normalized_region = normalize_region_name(payload.geography)
    known_region = normalized_region in _known_region_names()
    lookup_region = normalized_region if known_region else catalog.default_region
    if not known_region and (payload.geography or "").strip():
        _append_unique(
            warnings,
            f"Регион «{payload.geography}» не найден в demo/reference каталоге бюджета; "
            f"использован регион по умолчанию «{catalog.default_region}».",
        )

    item = _find_item(catalog, category_key=category_key, region=lookup_region)
    used_region = lookup_region
    if item is None:
        item, used_region = _find_default_item(catalog, category_key=category_key)
        if normalized_region != used_region and known_region:
            _append_unique(
                warnings,
                f"Для части статей бюджета использован регион по умолчанию «{used_region}».",
            )
    if item is None and category_key != OTHER_CATEGORY_KEY:
        item, used_region = _find_default_item(catalog, category_key=OTHER_CATEGORY_KEY)
        _append_unique(
            warnings,
            "Для части статей бюджета использована fallback-категория «Прочие расходы».",
        )
    if item is None:
        raise BudgetCatalogError(f"catalog has no fallback item for category {category_key}")

    return (
        FinancialItem(
            category=item.category_name,
            amount=round(item.avg_price, -3),
            comment=_provenance_comment(catalog, item, region=used_region),
        ),
        warnings,
    )


def _estimate_financial_items_emergency_fallback(
    payload: ProjectPlannerInput,
) -> list[FinancialItem]:
    coefficient = region_coefficient(payload.geography)
    region = normalize_region_name(payload.geography)
    return [
        FinancialItem(
            category=category,
            amount=round(base_amount * coefficient, -3),
            comment=(
                "Источник: emergency fallback; каталог: hardcoded MVP estimates; "
                f"дата: n/a; регион: {region}; confidence: test."
            ),
        )
        for category, base_amount in BUDGET_BASE_ITEMS.items()
    ]


def resolve_budget_items(
    payload: ProjectPlannerInput,
    *,
    catalog: BudgetCatalog | None = None,
    categories: tuple[str, ...] = STANDARD_BUDGET_CATEGORY_KEYS,
) -> BudgetResolution:
    warnings: list[str] = []
    try:
        active_catalog = catalog or load_builtin_budget_catalog()
        financial_items: list[FinancialItem] = []
        for category in categories:
            item, item_warnings = resolve_budget_item(category, payload, active_catalog)
            financial_items.append(item)
            for warning in item_warnings:
                _append_unique(warnings, warning)
        return BudgetResolution(financial_items=financial_items, warnings=warnings)
    except Exception:
        logger.warning(
            "Project Planner budget catalog failed; using emergency fallback.",
            exc_info=True,
        )
        return BudgetResolution(
            financial_items=_estimate_financial_items_emergency_fallback(payload),
            warnings=[CATALOG_EMERGENCY_FALLBACK_WARNING],
            used_emergency_fallback=True,
        )
