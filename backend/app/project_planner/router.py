from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.project_planner.schemas import (
    ClarificationResponse,
    ProjectPlannerInput,
    ProjectPlannerRunCreate,
    ProjectPlannerRunDetail,
    ProjectPlannerRunResponse,
    ProjectPlannerRunSummary,
)
from app.project_planner.service import (
    create_project_planner_run,
    get_docx_path,
    get_project_planner_run,
    list_project_planner_runs,
)
from app.project_planner.validators import build_clarifications

router = APIRouter(prefix="/project-planner")


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
