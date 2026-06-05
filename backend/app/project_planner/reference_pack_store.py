from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import app.project_planner.reference_packs as reference_packs
from app.project_planner.reference_packs import (
    ReferencePack,
    load_reference_packs,
    parse_reference_pack,
)


class ReferencePackInstallError(ValueError):
    pass


def reference_pack_directory() -> Path:
    return reference_packs.DEFAULT_REFERENCE_PACK_DIR


def sanitize_reference_pack_filename(pack_name: str) -> str:
    raw_name = str(pack_name or "")
    normalized = raw_name.strip().lower()
    safe = re.sub(r"[^a-z0-9_-]+", "-", normalized)
    safe = re.sub(r"-{2,}", "-", safe)
    safe = re.sub(r"_{2,}", "_", safe)
    stem = safe.strip("-_")
    if not stem:
        digest = hashlib.sha1(raw_name.encode("utf-8")).hexdigest()[:8]
        stem = f"reference-pack-{digest}"
    return f"{stem}.json"


def _validate_target_filename(filename: str) -> str:
    if not isinstance(filename, str) or not filename.strip():
        raise ReferencePackInstallError("filename must be a non-empty string")
    value = filename.strip()
    if Path(value).is_absolute() or "/" in value or "\\" in value:
        raise ReferencePackInstallError("filename must not contain path separators")
    if not value.endswith(".json"):
        raise ReferencePackInstallError("filename must use .json extension")
    stem = value[: -len(".json")]
    if not stem or stem in {".", ".."}:
        raise ReferencePackInstallError("filename stem must be non-empty")
    return value


def validate_reference_pack_file(path: Path) -> ReferencePack:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_reference_pack_data(raw)


def validate_reference_pack_data(raw: dict[str, Any]) -> ReferencePack:
    return parse_reference_pack(raw)


def reference_pack_to_dict(pack: ReferencePack) -> dict[str, Any]:
    result: dict[str, Any] = {
        "pack_name": pack.pack_name,
        "pack_version": pack.pack_version,
        "source_name": pack.source_name,
        "source_date": pack.source_date,
        "confidence": pack.confidence,
        "scope": {
            "project_types": list(pack.scope.project_types),
            "regions": list(pack.scope.regions),
            "keywords": list(pack.scope.keywords),
        },
        "facts": [
            {
                "title": fact.title,
                "text": fact.text,
            }
            for fact in pack.facts
        ],
    }
    if pack.constraints:
        result["constraints"] = list(pack.constraints)
    concept_guidelines: dict[str, list[str]] = {}
    if pack.concept_prefer:
        concept_guidelines["prefer"] = list(pack.concept_prefer)
    if pack.concept_avoid:
        concept_guidelines["avoid"] = list(pack.concept_avoid)
    if concept_guidelines:
        result["concept_guidelines"] = concept_guidelines
    if pack.resource_notes:
        result["resource_notes"] = list(pack.resource_notes)
    if pack.budget_notes:
        result["budget_notes"] = list(pack.budget_notes)
    return result


def _install_parsed_reference_pack(
    pack: ReferencePack,
    *,
    target_dir: Path | None = None,
    filename: str | None = None,
    replace: bool = False,
) -> Path:
    output_filename = (
        _validate_target_filename(filename)
        if filename is not None
        else sanitize_reference_pack_filename(pack.pack_name)
    )
    root = target_dir or reference_pack_directory()
    target = root / output_filename
    if target.exists() and not replace:
        raise ReferencePackInstallError(f"reference pack already exists: {target}")

    root.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=root,
            prefix=f".{target.stem}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            payload = json.dumps(
                reference_pack_to_dict(pack),
                ensure_ascii=False,
                indent=2,
            )
            temp_file.write(payload)
            temp_file.write("\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())
        temp_path.replace(target)
    except Exception:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise
    return target


def install_reference_pack(
    source_path: Path,
    *,
    target_dir: Path | None = None,
    filename: str | None = None,
    replace: bool = False,
) -> Path:
    pack = validate_reference_pack_file(source_path)
    return _install_parsed_reference_pack(
        pack,
        target_dir=target_dir,
        filename=filename,
        replace=replace,
    )


def install_reference_pack_data(
    raw: dict[str, Any],
    *,
    target_dir: Path | None = None,
    filename: str | None = None,
    replace: bool = False,
) -> Path:
    pack = validate_reference_pack_data(raw)
    return _install_parsed_reference_pack(
        pack,
        target_dir=target_dir,
        filename=filename,
        replace=replace,
    )


def list_installed_reference_packs(
    target_dir: Path | None = None,
) -> list[ReferencePack]:
    return load_reference_packs(target_dir or reference_pack_directory())
