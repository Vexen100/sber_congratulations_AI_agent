from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

import app.project_planner.reference_packs as reference_packs
from app.core.config import settings
from app.llm.provider import LLMResponse
from app.project_planner.budget import BUDGET_CONCEPT_COST_ALIGNMENT_WARNING
from app.project_planner.generator import generate_project_report
from app.project_planner.mock_generator import build_mock_report
from app.project_planner.prompts import (
    PROJECT_REPORT_JSON_SKELETON_TEXT,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from app.project_planner.reference_packs import (
    MAX_PROMPT_CONTEXT_LENGTH,
    REFERENCE_CONTEXT_INSTRUCTION,
    ReferencePackError,
    build_reference_pack_prompt_context,
    load_reference_packs,
    parse_reference_pack,
    select_reference_packs,
)
from app.project_planner.schemas import ProjectPlannerInput


def _payload() -> ProjectPlannerInput:
    return ProjectPlannerInput(
        idea="Провести фестиваль талантов для сотрудников Уральского банка",
        deadline=dt.date.today() + dt.timedelta(days=90),
        budget=1_500_000,
        geography="Свердловская область",
        stakeholders="HR, руководители направлений, сотрудники банка",
        current_resources="Внутренний портал, рассылки и площадки банка",
        technology_constraints="Использовать только согласованные внутренние каналы",
        project_accents="Учесть 185-летие Сбера и идеи фестиваля",
    )


def _neutral_payload() -> ProjectPlannerInput:
    return ProjectPlannerInput(
        idea="Подготовить управляемую инициативу для внутреннего согласования",
        deadline=dt.date.today() + dt.timedelta(days=90),
        geography="Пермский край",
        stakeholders="Бизнес-заказчик и проектная команда",
        current_resources="Базовая команда проекта",
        project_accents="Собрать понятный MVP-план",
    )


def _pack(
    *,
    pack_name: str = "ural_bank_internal_events",
    regions: list[str] | None = None,
    keywords: list[str] | None = None,
    facts: list[dict] | None = None,
    constraints: list[str] | None = None,
    resource_notes: list[str] | None = None,
    budget_notes: list[str] | None = None,
    concept_guidelines: dict | None = None,
) -> dict:
    return {
        "pack_name": pack_name,
        "pack_version": "v1",
        "source_name": "Локальный справочник проекта",
        "source_date": "2026-06-01",
        "confidence": "customer_reference",
        "scope": {
            "project_types": ["event"],
            "regions": regions if regions is not None else ["Свердловская область"],
            "keywords": keywords if keywords is not None else ["фестиваль", "таланты"],
        },
        "facts": (
            facts
            if facts is not None
            else [
                {
                    "title": "Внутренние каналы",
                    "text": (
                        "Для коммуникаций использовать внутренний портал, рассылки и "
                        "согласованные HR-каналы."
                    ),
                }
            ]
        ),
        "constraints": (
            constraints
            if constraints is not None
            else ["Не использовать несогласованные публичные каналы коммуникаций."]
        ),
        "concept_guidelines": (
            concept_guidelines
            if concept_guidelines is not None
            else {
                "prefer": ["форматы с вовлечением сотрудников"],
                "avoid": ["концепции, требующие внешней публичной рекламы"],
            }
        ),
        "resource_notes": (
            resource_notes
            if resource_notes is not None
            else ["Площадки банка могут использоваться как базовый ресурс."]
        ),
        "budget_notes": (
            budget_notes
            if budget_notes is not None
            else [
                (
                    "Цены из reference pack не являются финансовым источником; бюджет "
                    "считать backend budget catalog."
                )
            ]
        ),
    }


def _write_pack(directory: Path, filename: str, payload: dict) -> Path:
    path = directory / filename
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


class FakeJsonProvider:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls = 0

    async def generate_text(self, messages: list[dict], **kwargs) -> LLMResponse:  # noqa: ARG002
        self.calls += 1
        return LLMResponse(
            content=json.dumps(self.payload, ensure_ascii=False),
            model_name="fake-json",
        )


def test_reference_packs_missing_directory_returns_empty(tmp_path):
    missing = tmp_path / "missing"

    assert load_reference_packs(missing) == []
    assert build_reference_pack_prompt_context(_payload(), directory=missing) == ""


def test_reference_packs_load_valid_pack_and_ignore_non_json(tmp_path):
    _write_pack(tmp_path, "pack.json", _pack())
    (tmp_path / "notes.txt").write_text("ignore me", encoding="utf-8")

    packs = load_reference_packs(tmp_path)

    assert len(packs) == 1
    assert packs[0].pack_name == "ural_bank_internal_events"
    assert packs[0].facts[0].title == "Внутренние каналы"


def test_reference_packs_skip_invalid_json_and_pack_safely(tmp_path, caplog):
    _write_pack(tmp_path, "valid.json", _pack(pack_name="valid_pack"))
    (tmp_path / "broken.json").write_text("{not-json", encoding="utf-8")
    invalid = _pack(pack_name="invalid_pack")
    invalid.pop("source_name")
    _write_pack(tmp_path, "invalid.json", invalid)

    packs = load_reference_packs(tmp_path)

    assert [pack.pack_name for pack in packs] == ["valid_pack"]
    assert "Skipping invalid Project Planner reference pack" in caplog.text
    assert build_reference_pack_prompt_context(_payload(), directory=tmp_path)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data.pop("pack_name"),
        lambda data: data.update({"source_date": "01.06.2026"}),
        lambda data: data.update({"facts": []}),
        lambda data: data["facts"][0].pop("title"),
        lambda data: data["facts"][0].update({"text": ""}),
        lambda data: data.update({"facts": [{"title": "t", "text": "x"}] * 21}),
        lambda data: data["facts"][0].update({"text": "x" * 501}),
        lambda data: data.update({"constraints": ["x" * 501]}),
        lambda data: data.update({"resource_notes": ["x" * 501]}),
    ],
)
def test_reference_pack_validation_rejects_invalid_structure(mutate):
    data = _pack()
    mutate(data)

    with pytest.raises(ReferencePackError):
        parse_reference_pack(data)


def test_reference_pack_selection_uses_region_and_keywords(tmp_path):
    _write_pack(tmp_path, "event.json", _pack(pack_name="event_pack"))
    packs = load_reference_packs(tmp_path)

    selected = select_reference_packs(_payload(), packs)

    assert [pack.pack_name for pack in selected] == ["event_pack"]


def test_reference_pack_selection_neutral_payload_selects_no_keyword_pack(tmp_path):
    _write_pack(tmp_path, "event.json", _pack(pack_name="event_pack"))
    packs = load_reference_packs(tmp_path)

    assert select_reference_packs(_neutral_payload(), packs) == []


def test_reference_pack_selection_allows_exact_region_only_pack(tmp_path):
    _write_pack(
        tmp_path,
        "region.json",
        _pack(
            pack_name="region_only_pack",
            regions=["Пермский край"],
            keywords=[],
        ),
    )
    packs = load_reference_packs(tmp_path)

    selected = select_reference_packs(_neutral_payload(), packs)

    assert [pack.pack_name for pack in selected] == ["region_only_pack"]


def test_reference_pack_selection_limits_and_orders_deterministically(tmp_path):
    _write_pack(
        tmp_path,
        "b_non_exact.json",
        _pack(pack_name="b_non_exact", regions=[], keywords=["сотрудников"]),
    )
    _write_pack(
        tmp_path,
        "a_exact_one.json",
        _pack(pack_name="a_exact_one", keywords=["сотрудников"]),
    )
    _write_pack(
        tmp_path,
        "c_exact_two.json",
        _pack(pack_name="c_exact_two", keywords=["сотрудников", "банка"]),
    )
    _write_pack(
        tmp_path,
        "d_exact_one.json",
        _pack(pack_name="d_exact_one", keywords=["банка"]),
    )
    packs = load_reference_packs(tmp_path)

    selected = select_reference_packs(_payload(), packs)

    assert [pack.pack_name for pack in selected] == [
        "c_exact_two",
        "a_exact_one",
        "d_exact_one",
    ]


def test_reference_pack_prompt_context_is_compact_structured_and_safe(tmp_path):
    _write_pack(tmp_path, "event.json", _pack())

    context = build_reference_pack_prompt_context(_payload(), directory=tmp_path)

    assert "Reference pack context" in context
    assert REFERENCE_CONTEXT_INSTRUCTION in context
    assert "ural_bank_internal_events v1" in context
    assert "Локальный справочник проекта" in context
    assert "2026-06-01" in context
    assert "customer_reference" in context
    assert "Внутренние каналы" in context
    assert "Reference constraints" in context
    assert "Concept preferences" in context
    assert "Resource notes" in context
    assert "Budget caveat" in context
    assert (
        "Budget notes are non-price assumptions; financial estimate is calculated "
        "by backend budget catalog."
    ) in context
    assert "Цены из reference pack" not in context
    assert '"pack_name"' not in context
    assert '"facts"' not in context
    assert len(context) <= MAX_PROMPT_CONTEXT_LENGTH


def test_reference_pack_prompt_context_truncates_deterministically(tmp_path):
    long_fact = {"title": "Факт", "text": "x" * 500}
    for index in range(3):
        _write_pack(
            tmp_path,
            f"pack_{index}.json",
            _pack(
                pack_name=f"pack_{index}",
                facts=[long_fact] * 20,
                resource_notes=["resource note " + "r" * 200],
                budget_notes=["budget note " + "b" * 200],
            ),
        )

    context = build_reference_pack_prompt_context(_payload(), directory=tmp_path)

    assert len(context) <= MAX_PROMPT_CONTEXT_LENGTH
    assert "budget note" not in context
    assert "resource note" not in context
    assert "Reference pack context" in context


def test_build_user_prompt_includes_reference_context_without_changing_skeleton(
    tmp_path,
    monkeypatch,
):
    _write_pack(tmp_path, "event.json", _pack())
    monkeypatch.setattr(reference_packs, "DEFAULT_REFERENCE_PACK_DIR", tmp_path)
    skeleton_before = PROJECT_REPORT_JSON_SKELETON_TEXT

    prompt = build_user_prompt(_payload())

    assert PROJECT_REPORT_JSON_SKELETON_TEXT == skeleton_before
    assert PROJECT_REPORT_JSON_SKELETON_TEXT in SYSTEM_PROMPT
    assert "Reference pack context" in prompt
    assert "Внутренние каналы" in prompt
    assert '"pack_name"' not in prompt


@pytest.mark.asyncio
async def test_reference_packs_do_not_mutate_report_budget_or_warnings(tmp_path, monkeypatch):
    _write_pack(tmp_path, "event.json", _pack())
    monkeypatch.setattr(reference_packs, "DEFAULT_REFERENCE_PACK_DIR", tmp_path)
    monkeypatch.setattr(settings, "project_planner_use_mock_llm", False, raising=False)
    monkeypatch.setattr(settings, "gigachat_retry_count", 0, raising=False)
    payload = _payload()
    raw = build_mock_report(payload).model_dump(mode="json")
    provider = FakeJsonProvider(raw)

    report, model_name, used_fallback = await generate_project_report(payload, provider=provider)

    warnings_text = "\n".join(report.warnings)
    assert used_fallback is False
    assert model_name == "fake-json"
    assert provider.calls == 1
    assert report.resources.financial_total == sum(
        item.amount for item in report.resources.financial_items
    )
    assert BUDGET_CONCEPT_COST_ALIGNMENT_WARNING in report.warnings
    assert "reference pack" not in warnings_text.lower()
    assert "Цены из reference pack" not in warnings_text
