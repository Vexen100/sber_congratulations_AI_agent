from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import httpx
import pytest

import app.project_planner.generator as generator
import app.project_planner.reference_packs as reference_packs
from app.db.session import get_session
from app.main import create_app
from app.project_planner.schemas import ProjectPlannerInput


def _payload() -> ProjectPlannerInput:
    return ProjectPlannerInput(
        idea="Провести фестиваль талантов для сотрудников Уральского банка",
        deadline=dt.date.today() + dt.timedelta(days=90),
        budget=1_500_000,
        geography="Свердловская область",
        stakeholders="HR, руководители направлений, сотрудники банка",
        current_resources="Внутренний портал и площадки банка",
        technology_constraints="Использовать только внутренние каналы",
        project_accents="Учесть 185-летие Сбера и фестиваль",
    )


def _neutral_payload() -> ProjectPlannerInput:
    return ProjectPlannerInput(
        idea="Подготовить управляемую инициативу",
        deadline=dt.date.today() + dt.timedelta(days=90),
        geography="Пермский край",
        stakeholders="Команда проекта",
        current_resources="Базовые ресурсы",
        project_accents="Собрать MVP-план",
    )


def _pack(
    *,
    pack_name: str = "ural_bank_internal_events",
    regions: list[str] | None = None,
    keywords: list[str] | None = None,
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
            "keywords": keywords if keywords is not None else ["фестиваль"],
        },
        "facts": [
            {
                "title": "Секретный факт справочника",
                "text": "RAW_FACT_TEXT_SHOULD_NOT_LEAK",
            }
        ],
        "constraints": ["RAW_CONSTRAINT_TEXT_SHOULD_NOT_LEAK"],
        "concept_guidelines": {
            "prefer": ["вовлечение сотрудников"],
            "avoid": ["внешняя публичная реклама"],
        },
        "resource_notes": ["RAW_RESOURCE_NOTE_SHOULD_NOT_LEAK"],
        "budget_notes": ["RAW_BUDGET_NOTE_SHOULD_NOT_LEAK"],
    }


def _write_pack(directory: Path, filename: str, payload: dict) -> Path:
    path = directory / filename
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _build_test_client(db_session):
    app = create_app()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    return app, client


async def test_reference_pack_api_list_missing_directory_returns_empty(
    db_session,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        reference_packs,
        "DEFAULT_REFERENCE_PACK_DIR",
        tmp_path / "missing",
    )
    app, client = _build_test_client(db_session)

    async with client:
        response = await client.get("/api/project-planner/reference-packs")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"items": [], "count": 0}


async def test_reference_pack_api_list_returns_metadata_without_raw_content(
    db_session,
    monkeypatch,
    tmp_path,
):
    _write_pack(tmp_path, "event.json", _pack())
    monkeypatch.setattr(reference_packs, "DEFAULT_REFERENCE_PACK_DIR", tmp_path)
    app, client = _build_test_client(db_session)

    async with client:
        response = await client.get("/api/project-planner/reference-packs")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    assert payload["items"] == [
        {
            "pack_name": "ural_bank_internal_events",
            "pack_version": "v1",
            "source_name": "Локальный справочник проекта",
            "source_date": "2026-06-01",
            "confidence": "customer_reference",
            "regions": ["Свердловская область"],
            "keywords": ["фестиваль"],
            "project_types": ["event"],
            "facts_count": 1,
            "constraints_count": 1,
            "concept_prefer_count": 1,
            "concept_avoid_count": 1,
            "resource_notes_count": 1,
            "has_budget_notes": True,
        }
    ]
    response_text = json.dumps(payload, ensure_ascii=False)
    assert "event.json" not in response_text
    assert str(tmp_path) not in response_text
    assert "RAW_FACT_TEXT_SHOULD_NOT_LEAK" not in response_text
    assert "RAW_CONSTRAINT_TEXT_SHOULD_NOT_LEAK" not in response_text
    assert "RAW_RESOURCE_NOTE_SHOULD_NOT_LEAK" not in response_text
    assert "RAW_BUDGET_NOTE_SHOULD_NOT_LEAK" not in response_text


async def test_reference_pack_api_skips_invalid_pack_and_still_returns_200(
    db_session,
    monkeypatch,
    tmp_path,
):
    _write_pack(tmp_path, "valid.json", _pack(pack_name="valid_pack"))
    (tmp_path / "broken.json").write_text("{not-json", encoding="utf-8")
    invalid = _pack(pack_name="invalid_pack")
    invalid["facts"] = []
    _write_pack(tmp_path, "invalid.json", invalid)
    monkeypatch.setattr(reference_packs, "DEFAULT_REFERENCE_PACK_DIR", tmp_path)
    app, client = _build_test_client(db_session)

    async with client:
        response = await client.get("/api/project-planner/reference-packs")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["pack_name"] == "valid_pack"


async def test_reference_pack_api_validate_pack_returns_metadata_without_writing(
    db_session,
    monkeypatch,
    tmp_path,
):
    target_dir = tmp_path / "reference_packs"
    monkeypatch.setattr(reference_packs, "DEFAULT_REFERENCE_PACK_DIR", target_dir)
    app, client = _build_test_client(db_session)

    async with client:
        response = await client.post(
            "/api/project-planner/reference-packs/validate",
            json={"pack": _pack()},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["suggested_filename"] == "ural_bank_internal_events.json"
    assert body["item"]["pack_name"] == "ural_bank_internal_events"
    assert body["item"]["facts_count"] == 1
    assert not target_dir.exists()
    response_text = json.dumps(body, ensure_ascii=False)
    assert "RAW_FACT_TEXT_SHOULD_NOT_LEAK" not in response_text
    assert "RAW_CONSTRAINT_TEXT_SHOULD_NOT_LEAK" not in response_text
    assert "RAW_BUDGET_NOTE_SHOULD_NOT_LEAK" not in response_text


async def test_reference_pack_api_validate_rejects_too_large_pack(
    db_session,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(reference_packs, "DEFAULT_REFERENCE_PACK_DIR", tmp_path)
    oversized = _pack()
    oversized["unused_large_field"] = "x" * (257 * 1024)
    app, client = _build_test_client(db_session)

    async with client:
        response = await client.post(
            "/api/project-planner/reference-packs/validate",
            json={"pack": oversized},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 413
    assert "256 KB" in response.json()["detail"]


async def test_reference_pack_api_install_pack_creates_file_and_list_sees_it(
    db_session,
    monkeypatch,
    tmp_path,
):
    target_dir = tmp_path / "reference_packs"
    monkeypatch.setattr(reference_packs, "DEFAULT_REFERENCE_PACK_DIR", target_dir)
    app, client = _build_test_client(db_session)

    async with client:
        install_response = await client.post(
            "/api/project-planner/reference-packs/install",
            json={"pack": _pack()},
        )
        list_response = await client.get("/api/project-planner/reference-packs")
    app.dependency_overrides.clear()

    assert install_response.status_code == 200
    body = install_response.json()
    assert body["installed"] is True
    assert body["stored_filename"] == "ural_bank_internal_events.json"
    assert body["item"]["pack_name"] == "ural_bank_internal_events"
    assert str(target_dir) not in json.dumps(body, ensure_ascii=False)
    assert (target_dir / "ural_bank_internal_events.json").exists()
    installed_data = json.loads(
        (target_dir / "ural_bank_internal_events.json").read_text(encoding="utf-8")
    )
    assert installed_data["pack_name"] == "ural_bank_internal_events"
    assert list_response.status_code == 200
    assert list_response.json()["count"] == 1
    assert list_response.json()["items"][0]["pack_name"] == "ural_bank_internal_events"


async def test_reference_pack_api_install_duplicate_requires_explicit_replace(
    db_session,
    monkeypatch,
    tmp_path,
):
    target_dir = tmp_path / "reference_packs"
    monkeypatch.setattr(reference_packs, "DEFAULT_REFERENCE_PACK_DIR", target_dir)
    replacement = _pack()
    replacement["source_name"] = "Обновлённый источник"
    app, client = _build_test_client(db_session)

    async with client:
        first = await client.post(
            "/api/project-planner/reference-packs/install",
            json={"pack": _pack()},
        )
        duplicate = await client.post(
            "/api/project-planner/reference-packs/install",
            json={"pack": replacement},
        )
        replaced = await client.post(
            "/api/project-planner/reference-packs/install",
            json={"pack": replacement, "replace": True},
        )
    app.dependency_overrides.clear()

    assert first.status_code == 200
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Справочник с таким именем уже установлен."
    assert str(target_dir) not in json.dumps(duplicate.json(), ensure_ascii=False)
    assert replaced.status_code == 200
    assert replaced.json()["item"]["source_name"] == "Обновлённый источник"
    stored = json.loads((target_dir / "ural_bank_internal_events.json").read_text("utf-8"))
    assert stored["source_name"] == "Обновлённый источник"


async def test_reference_pack_api_install_rejects_invalid_pack_without_traceback(
    db_session,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(reference_packs, "DEFAULT_REFERENCE_PACK_DIR", tmp_path)
    invalid = _pack()
    invalid["facts"] = []
    app, client = _build_test_client(db_session)

    async with client:
        response = await client.post(
            "/api/project-planner/reference-packs/install",
            json={"pack": invalid},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 422
    response_text = json.dumps(response.json(), ensure_ascii=False)
    assert "Reference pack is invalid" in response_text
    assert "Traceback" not in response_text


async def test_reference_pack_api_install_rejects_unsafe_filename(
    db_session,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(reference_packs, "DEFAULT_REFERENCE_PACK_DIR", tmp_path)
    app, client = _build_test_client(db_session)

    async with client:
        response = await client.post(
            "/api/project-planner/reference-packs/install",
            json={"pack": _pack(), "filename": "../x.json"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "path separators" in response.json()["detail"]


async def test_reference_pack_api_install_does_not_create_run_or_call_llm(
    db_session,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(reference_packs, "DEFAULT_REFERENCE_PACK_DIR", tmp_path)

    def fail_provider_call():
        pytest.fail("reference pack install must not request an LLM provider")

    monkeypatch.setattr(generator, "get_project_planner_llm_provider", fail_provider_call)
    app, client = _build_test_client(db_session)

    async with client:
        before = await client.get("/api/project-planner/runs")
        install_response = await client.post(
            "/api/project-planner/reference-packs/install",
            json={"pack": _pack()},
        )
        after = await client.get("/api/project-planner/runs")
    app.dependency_overrides.clear()

    assert before.status_code == 200
    assert install_response.status_code == 200
    assert after.status_code == 200
    assert before.json() == []
    assert after.json() == []


async def test_reference_pack_api_selection_preview_returns_selected_metadata(
    db_session,
    monkeypatch,
    tmp_path,
):
    _write_pack(tmp_path, "event.json", _pack())
    monkeypatch.setattr(reference_packs, "DEFAULT_REFERENCE_PACK_DIR", tmp_path)
    packs = reference_packs.load_reference_packs(tmp_path)
    selected = reference_packs.select_reference_packs(_payload(), packs)
    expected_context = reference_packs.build_reference_pack_prompt_context_from_packs(selected)

    def fail_old_context_helper(*args, **kwargs):  # noqa: ANN002, ANN003
        pytest.fail("selection preview must build context from already selected packs")

    monkeypatch.setattr(
        reference_packs,
        "build_reference_pack_prompt_context",
        fail_old_context_helper,
    )
    app, client = _build_test_client(db_session)

    async with client:
        response = await client.post(
            "/api/project-planner/reference-packs/selection-preview",
            json=_payload().model_dump(mode="json"),
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["items"][0]["pack_name"] == "ural_bank_internal_events"
    assert body["reference_context_length"] == len(expected_context)
    assert body["reference_context_length"] > 0
    assert "reference_context" not in body
    response_text = json.dumps(body, ensure_ascii=False)
    assert "RAW_FACT_TEXT_SHOULD_NOT_LEAK" not in response_text
    assert "RAW_CONSTRAINT_TEXT_SHOULD_NOT_LEAK" not in response_text
    assert "RAW_BUDGET_NOTE_SHOULD_NOT_LEAK" not in response_text


async def test_reference_pack_api_selection_preview_neutral_payload_returns_empty(
    db_session,
    monkeypatch,
    tmp_path,
):
    _write_pack(tmp_path, "event.json", _pack())
    monkeypatch.setattr(reference_packs, "DEFAULT_REFERENCE_PACK_DIR", tmp_path)
    app, client = _build_test_client(db_session)

    async with client:
        response = await client.post(
            "/api/project-planner/reference-packs/selection-preview",
            json=_neutral_payload().model_dump(mode="json"),
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "count": 0,
        "reference_context_length": 0,
    }


async def test_reference_pack_api_selection_preview_does_not_create_run_or_call_llm(
    db_session,
    monkeypatch,
    tmp_path,
):
    _write_pack(tmp_path, "event.json", _pack())
    monkeypatch.setattr(reference_packs, "DEFAULT_REFERENCE_PACK_DIR", tmp_path)

    def fail_provider_call():
        pytest.fail("selection preview must not request an LLM provider")

    monkeypatch.setattr(generator, "get_project_planner_llm_provider", fail_provider_call)
    app, client = _build_test_client(db_session)

    async with client:
        before = await client.get("/api/project-planner/runs")
        preview = await client.post(
            "/api/project-planner/reference-packs/selection-preview",
            json=_payload().model_dump(mode="json"),
        )
        after = await client.get("/api/project-planner/runs")
    app.dependency_overrides.clear()

    assert before.status_code == 200
    assert preview.status_code == 200
    assert after.status_code == 200
    assert before.json() == []
    assert after.json() == []
