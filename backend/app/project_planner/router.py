from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.project_planner.pptx_export import PPTX_MEDIA_TYPE, export_project_report_pptx
from app.project_planner.reference_pack_store import (
    ReferencePackInstallError,
    install_reference_pack_data,
    sanitize_reference_pack_filename,
    validate_reference_pack_data,
)
from app.project_planner.reference_packs import (
    ReferencePackError,
    build_reference_pack_prompt_context_from_packs,
    load_reference_packs,
    reference_pack_metadata,
    select_reference_packs,
)
from app.project_planner.schemas import (
    ClarificationResponse,
    ProjectPlannerInput,
    ProjectPlannerRunCreate,
    ProjectPlannerRunDetail,
    ProjectPlannerRunResponse,
    ProjectPlannerRunSummary,
    ReferencePackListResponse,
    ReferencePackSelectionPreviewResponse,
    ReferencePackUploadRequest,
    ReferencePackUploadResponse,
    ReferencePackValidateRequest,
    ReferencePackValidateResponse,
)
from app.project_planner.service import (
    create_project_planner_run,
    get_docx_path,
    get_project_planner_run,
    get_project_report_for_export,
    list_project_planner_runs,
)
from app.project_planner.validators import build_clarifications

router = APIRouter(prefix="/project-planner")
MAX_REFERENCE_PACK_UPLOAD_BYTES = 256 * 1024


def _ensure_reference_pack_size(raw: dict) -> None:
    size = len(json.dumps(raw, ensure_ascii=False).encode("utf-8"))
    if size > MAX_REFERENCE_PACK_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Reference pack JSON exceeds 256 KB limit.",
        )


def _reference_pack_validation_error(exc: ReferencePackError) -> HTTPException:
    return HTTPException(status_code=422, detail=f"Reference pack is invalid: {exc}")


def _reference_pack_install_error(exc: ReferencePackInstallError) -> HTTPException:
    if "already exists" in str(exc):
        return HTTPException(
            status_code=409,
            detail="Справочник с таким именем уже установлен.",
        )
    return HTTPException(status_code=400, detail=str(exc))


@router.post("/clarifications", response_model=ClarificationResponse)
async def clarify_project(payload: ProjectPlannerInput) -> ClarificationResponse:
    return build_clarifications(payload)


@router.post("/runs", response_model=ProjectPlannerRunResponse)
async def create_run(
    payload: ProjectPlannerRunCreate,
    session: AsyncSession = Depends(get_session),
) -> ProjectPlannerRunResponse:
    run = await create_project_planner_run(
        session,
        payload.input,
        generate_with_assumptions=payload.generate_with_assumptions,
    )
    return ProjectPlannerRunResponse(run=run)


@router.get("/runs", response_model=list[ProjectPlannerRunSummary])
async def list_runs(session: AsyncSession = Depends(get_session)) -> list[ProjectPlannerRunSummary]:
    return await list_project_planner_runs(session)


@router.get("/reference-packs", response_model=ReferencePackListResponse)
async def list_reference_packs() -> ReferencePackListResponse:
    items = [reference_pack_metadata(pack) for pack in load_reference_packs()]
    return ReferencePackListResponse(items=items, count=len(items))


@router.post(
    "/reference-packs/validate",
    response_model=ReferencePackValidateResponse,
)
async def validate_reference_pack(
    payload: ReferencePackValidateRequest,
) -> ReferencePackValidateResponse:
    _ensure_reference_pack_size(payload.pack)
    try:
        pack = validate_reference_pack_data(payload.pack)
    except ReferencePackError as exc:
        raise _reference_pack_validation_error(exc) from exc
    return ReferencePackValidateResponse(
        item=reference_pack_metadata(pack),
        suggested_filename=sanitize_reference_pack_filename(pack.pack_name),
    )


@router.post(
    "/reference-packs/install",
    response_model=ReferencePackUploadResponse,
)
async def install_reference_pack(
    payload: ReferencePackUploadRequest,
) -> ReferencePackUploadResponse:
    _ensure_reference_pack_size(payload.pack)
    try:
        pack = validate_reference_pack_data(payload.pack)
        target = install_reference_pack_data(
            payload.pack,
            filename=payload.filename,
            replace=payload.replace,
        )
    except ReferencePackError as exc:
        raise _reference_pack_validation_error(exc) from exc
    except ReferencePackInstallError as exc:
        raise _reference_pack_install_error(exc) from exc
    return ReferencePackUploadResponse(
        item=reference_pack_metadata(pack),
        stored_filename=target.name,
    )


@router.post(
    "/reference-packs/selection-preview",
    response_model=ReferencePackSelectionPreviewResponse,
)
async def preview_reference_pack_selection(
    payload: ProjectPlannerInput,
) -> ReferencePackSelectionPreviewResponse:
    packs = load_reference_packs()
    selected = select_reference_packs(payload, packs)
    context = build_reference_pack_prompt_context_from_packs(selected)
    items = [reference_pack_metadata(pack) for pack in selected]
    return ReferencePackSelectionPreviewResponse(
        items=items,
        count=len(items),
        reference_context_length=len(context),
    )


@router.get("/runs/{run_id}", response_model=ProjectPlannerRunDetail)
async def get_run(
    run_id: int,
    session: AsyncSession = Depends(get_session),
) -> ProjectPlannerRunDetail:
    return await get_project_planner_run(session, run_id)


@router.get("/runs/{run_id}/docx")
async def download_docx(run_id: int, session: AsyncSession = Depends(get_session)) -> FileResponse:
    path = await get_docx_path(session, run_id)
    return FileResponse(
        path,
        media_type=("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        filename=path.name,
    )


@router.get("/runs/{run_id}/pptx")
async def download_pptx(run_id: int, session: AsyncSession = Depends(get_session)) -> Response:
    report = await get_project_report_for_export(session, run_id)
    content = export_project_report_pptx(report)
    return Response(
        content=content,
        media_type=PPTX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="project-planner-run-{run_id}.pptx"'
        },
    )
