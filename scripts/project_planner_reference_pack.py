#!/usr/bin/env python3
# ruff: noqa: E402
# This CLI adds backend/ to sys.path before importing app modules.
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.project_planner.reference_pack_store import (  # noqa: E402
    ReferencePackInstallError,
    install_reference_pack,
    list_installed_reference_packs,
    validate_reference_pack_file,
)
from app.project_planner.reference_packs import (
    ReferencePack,
    ReferencePackError,
)  # noqa: E402


def _join_or_dash(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "-"


def _print_pack_metadata(pack: ReferencePack) -> None:
    print(f"pack_name: {pack.pack_name}")
    print(f"pack_version: {pack.pack_version}")
    print(f"source_name: {pack.source_name}")
    print(f"source_date: {pack.source_date}")
    print(f"confidence: {pack.confidence}")
    print(f"facts_count: {len(pack.facts)}")
    print(f"regions: {_join_or_dash(pack.scope.regions)}")
    print(f"keywords: {_join_or_dash(pack.scope.keywords)}")


def _expected_error(exc: Exception) -> bool:
    return isinstance(
        exc,
        (
            OSError,
            json.JSONDecodeError,
            ReferencePackError,
            ReferencePackInstallError,
        ),
    )


def _cmd_validate(args: argparse.Namespace) -> int:
    pack = validate_reference_pack_file(args.path)
    _print_pack_metadata(pack)
    return 0


def _cmd_install(args: argparse.Namespace) -> int:
    target = install_reference_pack(
        args.path,
        target_dir=args.target_dir,
        filename=args.filename,
        replace=args.replace,
    )
    pack = validate_reference_pack_file(target)
    print(f"installed_path: {target}")
    _print_pack_metadata(pack)
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    packs = list_installed_reference_packs(args.target_dir)
    if not packs:
        directory = args.target_dir or "default reference pack directory"
        print(f"No valid reference packs found in {directory}.")
        return 0
    for index, pack in enumerate(packs, start=1):
        if index > 1:
            print("")
        print(f"[{index}]")
        _print_pack_metadata(pack)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate, install, and list Project Planner reference packs."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("path", type=Path)
    validate_parser.set_defaults(handler=_cmd_validate)

    install_parser = subparsers.add_parser("install")
    install_parser.add_argument("path", type=Path)
    install_parser.add_argument("--target-dir", type=Path)
    install_parser.add_argument("--filename")
    install_parser.add_argument("--replace", action="store_true")
    install_parser.set_defaults(handler=_cmd_install)

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--target-dir", type=Path)
    list_parser.set_defaults(handler=_cmd_list)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except Exception as exc:
        if _expected_error(exc):
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        raise


if __name__ == "__main__":
    raise SystemExit(main())
