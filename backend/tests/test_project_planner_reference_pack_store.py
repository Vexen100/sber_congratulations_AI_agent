from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from app.project_planner.reference_pack_store import (
    ReferencePackInstallError,
    install_reference_pack,
    list_installed_reference_packs,
    reference_pack_directory,
    reference_pack_to_dict,
    sanitize_reference_pack_filename,
    validate_reference_pack_file,
)
from app.project_planner.reference_packs import (
    DEFAULT_REFERENCE_PACK_DIR,
    ReferencePackError,
    load_reference_packs,
)


def _pack(
    *,
    pack_name: str = "ural_bank_internal_events",
    source_name: str = "Локальный справочник проекта",
    facts: list[dict] | None = None,
    unknown: bool = False,
) -> dict:
    data = {
        "pack_name": pack_name,
        "pack_version": "v1",
        "source_name": source_name,
        "source_date": "2026-06-01",
        "confidence": "customer_reference",
        "scope": {
            "project_types": ["event"],
            "regions": ["Свердловская область"],
            "keywords": ["фестиваль"],
        },
        "facts": (
            facts
            if facts is not None
            else [
                {
                    "title": "Внутренние каналы",
                    "text": "Использовать внутренний портал и HR-рассылки.",
                }
            ]
        ),
        "constraints": ["Не использовать несогласованные публичные каналы."],
        "concept_guidelines": {
            "prefer": ["вовлечение сотрудников"],
            "avoid": ["внешняя публичная реклама"],
        },
        "resource_notes": ["Площадки банка доступны как базовый ресурс."],
        "budget_notes": ["Не использовать как price evidence."],
    }
    if unknown:
        data["unknown_field"] = "must be dropped"
    return data


def _write_json(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _load_cli_module():
    script_path = (
        Path(__file__).resolve().parents[2] / "scripts" / "project_planner_reference_pack.py"
    )
    module_name = "project_planner_reference_pack_cli_for_tests"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_reference_pack_directory_matches_loader_default():
    assert reference_pack_directory() == DEFAULT_REFERENCE_PACK_DIR


@pytest.mark.parametrize(
    ("pack_name", "expected"),
    [
        ("ural_bank_internal_events", "ural_bank_internal_events.json"),
        ("Pack 01: Internal Events", "pack-01-internal-events.json"),
    ],
)
def test_sanitize_reference_pack_filename_ascii(pack_name, expected):
    assert sanitize_reference_pack_filename(pack_name) == expected


def test_sanitize_reference_pack_filename_uses_deterministic_fallback_for_cyrillic():
    pack_name = "Фестиваль талантов"
    digest = hashlib.sha1(pack_name.encode("utf-8")).hexdigest()[:8]

    assert sanitize_reference_pack_filename(pack_name) == f"reference-pack-{digest}.json"


@pytest.mark.parametrize(
    "filename",
    [
        "../x.json",
        "nested/x.json",
        "/tmp/x.json",
        "pack.txt",
        ".json",
    ],
)
def test_install_rejects_unsafe_provided_filename(tmp_path, filename):
    source = _write_json(tmp_path / "source.json", _pack())
    target_dir = tmp_path / "installed"

    with pytest.raises(ReferencePackInstallError):
        install_reference_pack(source, target_dir=target_dir, filename=filename)

    assert not target_dir.exists()


def test_validate_reference_pack_file_accepts_valid_json(tmp_path):
    source = _write_json(tmp_path / "source.json", _pack())

    pack = validate_reference_pack_file(source)

    assert pack.pack_name == "ural_bank_internal_events"
    assert pack.scope.regions == ("Свердловская область",)


def test_validate_reference_pack_file_rejects_invalid_json(tmp_path):
    source = tmp_path / "broken.json"
    source.write_text("{not-json", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        validate_reference_pack_file(source)


def test_validate_reference_pack_file_rejects_invalid_pack(tmp_path):
    data = _pack()
    data.pop("source_name")
    source = _write_json(tmp_path / "invalid.json", data)

    with pytest.raises(ReferencePackError):
        validate_reference_pack_file(source)


def test_install_invalid_source_does_not_create_target_directory(tmp_path):
    data = _pack()
    data["facts"] = []
    source = _write_json(tmp_path / "invalid.json", data)
    target_dir = tmp_path / "installed"

    with pytest.raises(ReferencePackError):
        install_reference_pack(source, target_dir=target_dir)

    assert not target_dir.exists()
    assert not (target_dir / "ural_bank_internal_events.json").exists()


def test_install_creates_target_dir_and_writes_normalized_json(tmp_path):
    source = _write_json(tmp_path / "source.json", _pack(unknown=True))
    target_dir = tmp_path / "installed"

    target = install_reference_pack(source, target_dir=target_dir)

    assert target == target_dir / "ural_bank_internal_events.json"
    assert target_dir.exists()
    text = target.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert "Локальный справочник проекта" in text
    data = json.loads(text)
    assert "unknown_field" not in data
    assert list(data) == [
        "pack_name",
        "pack_version",
        "source_name",
        "source_date",
        "confidence",
        "scope",
        "facts",
        "constraints",
        "concept_guidelines",
        "resource_notes",
        "budget_notes",
    ]
    assert load_reference_packs(target_dir)[0].pack_name == "ural_bank_internal_events"


def test_reference_pack_to_dict_omits_empty_optional_arrays(tmp_path):
    data = _pack()
    data.pop("constraints")
    data.pop("concept_guidelines")
    data.pop("resource_notes")
    data.pop("budget_notes")
    source = _write_json(tmp_path / "source.json", data)
    pack = validate_reference_pack_file(source)

    serialized = reference_pack_to_dict(pack)

    assert "constraints" not in serialized
    assert "concept_guidelines" not in serialized
    assert "resource_notes" not in serialized
    assert "budget_notes" not in serialized


def test_install_rejects_existing_file_unless_replace_true(tmp_path):
    source = _write_json(tmp_path / "source.json", _pack(source_name="Первый источник"))
    target_dir = tmp_path / "installed"
    target = install_reference_pack(source, target_dir=target_dir)
    replacement = _write_json(
        tmp_path / "replacement.json",
        _pack(source_name="Второй источник"),
    )

    with pytest.raises(ReferencePackInstallError):
        install_reference_pack(replacement, target_dir=target_dir)

    assert json.loads(target.read_text(encoding="utf-8"))["source_name"] == "Первый источник"

    replaced = install_reference_pack(replacement, target_dir=target_dir, replace=True)

    assert replaced == target
    assert json.loads(target.read_text(encoding="utf-8"))["source_name"] == "Второй источник"


def test_install_custom_safe_filename(tmp_path):
    source = _write_json(tmp_path / "source.json", _pack())

    target = install_reference_pack(
        source,
        target_dir=tmp_path / "installed",
        filename="custom_pack.json",
    )

    assert target.name == "custom_pack.json"


def test_list_installed_reference_packs_missing_and_installed(tmp_path):
    target_dir = tmp_path / "missing"

    assert list_installed_reference_packs(target_dir) == []

    source = _write_json(tmp_path / "source.json", _pack())
    install_reference_pack(source, target_dir=target_dir)

    packs = list_installed_reference_packs(target_dir)

    assert [pack.pack_name for pack in packs] == ["ural_bank_internal_events"]


def test_cli_validate_valid_pack_returns_zero_and_prints_metadata(tmp_path, capsys):
    cli = _load_cli_module()
    source = _write_json(tmp_path / "source.json", _pack())

    result = cli.main(["validate", str(source)])

    output = capsys.readouterr()
    assert result == 0
    assert "pack_name: ural_bank_internal_events" in output.out
    assert "facts_count: 1" in output.out
    assert "Свердловская область" in output.out


def test_cli_validate_invalid_pack_returns_one_without_traceback(tmp_path, capsys):
    cli = _load_cli_module()
    source = tmp_path / "broken.json"
    source.write_text("{not-json", encoding="utf-8")

    result = cli.main(["validate", str(source)])

    output = capsys.readouterr()
    assert result == 1
    assert "Error:" in output.err
    assert "Traceback" not in output.err


def test_cli_install_into_target_dir_returns_zero_and_creates_file(tmp_path, capsys):
    cli = _load_cli_module()
    source = _write_json(tmp_path / "source.json", _pack())
    target_dir = tmp_path / "installed"

    result = cli.main(["install", str(source), "--target-dir", str(target_dir)])

    output = capsys.readouterr()
    assert result == 0
    assert "installed_path:" in output.out
    assert "pack_name: ural_bank_internal_events" in output.out
    assert (target_dir / "ural_bank_internal_events.json").exists()


def test_cli_list_installed_packs(tmp_path, capsys):
    cli = _load_cli_module()
    source = _write_json(tmp_path / "source.json", _pack())
    target_dir = tmp_path / "installed"
    install_reference_pack(source, target_dir=target_dir)

    result = cli.main(["list", "--target-dir", str(target_dir)])

    output = capsys.readouterr()
    assert result == 0
    assert "[1]" in output.out
    assert "pack_name: ural_bank_internal_events" in output.out


def test_cli_list_missing_or_empty_directory_returns_zero(tmp_path, capsys):
    cli = _load_cli_module()
    target_dir = tmp_path / "missing"

    result = cli.main(["list", "--target-dir", str(target_dir)])

    output = capsys.readouterr()
    assert result == 0
    assert "No valid reference packs found" in output.out
