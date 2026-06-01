from __future__ import annotations

import datetime as dt
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.project_planner.docx_export import export_project_report_docx
from app.project_planner.generator import generate_project_report
from app.project_planner.models import ProjectArtifact, ProjectPlannerRun, ProjectRequest
from app.project_planner.schemas import (
    ProjectArtifactOut,
    ProjectPlannerInput,
    ProjectPlannerRunDetail,
    ProjectPlannerRunSummary,
    ProjectReport,
)
from app.project_planner.validators import source_data_gaps


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _input_from_request(request: ProjectRequest) -> ProjectPlannerInput:
    return ProjectPlannerInput(
        idea=request.idea,
        deadline=request.deadline,
        budget=request.budget,
        geography=request.geography,
        stakeholders=request.stakeholders,
        current_resources=request.current_resources,
        technology_constraints=request.technology_constraints,
        project_accents=request.project_accents,
    )


def _report_from_run(run: ProjectPlannerRun) -> ProjectReport | None:
    if not run.result_json:
        return None
    return ProjectReport.model_validate(run.result_json)


def _run_title(run: ProjectPlannerRun) -> str:
    report = _report_from_run(run)
    if report is not None:
        return report.passport.title
    text = (run.request.idea or "").strip()
    return text[:90] if text else f"Project Planner run #{run.id}"


def _artifact_out(artifact: ProjectArtifact) -> ProjectArtifactOut:
    return ProjectArtifactOut(
        id=artifact.id,
        artifact_type=artifact.artifact_type,
        created_at=artifact.created_at,
    )


def _summary(run: ProjectPlannerRun) -> ProjectPlannerRunSummary:
    warnings = list(run.warnings_json or [])
    assumptions = list(run.assumptions_json or [])
    return ProjectPlannerRunSummary(
        id=run.id,
        request_id=run.request_id,
        status=run.status,
        model_name=run.model_name,
        created_at=run.created_at,
        finished_at=run.finished_at,
        title=_run_title(run),
        deadline=run.request.deadline,
        warnings_count=len(warnings),
        assumptions_count=len(assumptions),
        has_docx=any(artifact.artifact_type == "docx" for artifact in run.artifacts or []),
    )


def _detail(run: ProjectPlannerRun) -> ProjectPlannerRunDetail:
    report = _report_from_run(run)
    summary = _summary(run)
    return ProjectPlannerRunDetail(
        **summary.model_dump(),
        input=_input_from_request(run.request),
        report=report,
        warnings=list(run.warnings_json or []),
        assumptions=list(run.assumptions_json or []),
        artifacts=[
            _artifact_out(item) for item in sorted(run.artifacts or [], key=lambda item: item.id)
        ],
    )


async def create_project_planner_run(
    session: AsyncSession,
    payload: ProjectPlannerInput,
    *,
    generate_with_assumptions: bool = True,
) -> ProjectPlannerRunDetail:
    gaps = source_data_gaps(payload)
    if gaps and not generate_with_assumptions:
        raise HTTPException(
            status_code=422,
            detail=(
                "Недостаточно исходных данных для генерации без допущений: "
                f"{'; '.join(gaps)}. Разрешите генерацию с допущениями или уточните ввод."
            ),
        )

    request = ProjectRequest(
        idea=(payload.idea or "").strip(),
        deadline=payload.deadline,
        budget=payload.budget,
        geography=(payload.geography or "").strip() or None,
        stakeholders=(payload.stakeholders or "").strip() or None,
        current_resources=(payload.current_resources or "").strip() or None,
        technology_constraints=(payload.technology_constraints or "").strip() or None,
        project_accents=(payload.project_accents or "").strip() or None,
    )
    session.add(request)
    await session.commit()
    await session.refresh(request)

    run = ProjectPlannerRun(
        request_id=request.id,
        status="running",
        model_name=None,
        created_at=_now(),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    try:
        report, model_name, used_fallback = await generate_project_report(payload)
        run.result_json = report.model_dump(mode="json")
        run.warnings_json = report.warnings
        run.assumptions_json = report.assumptions
        run.status = "fallback" if used_fallback and model_name != "mock" else "success"
        run.model_name = model_name
        run.finished_at = _now()
        await session.commit()
        await session.refresh(run)

        docx_path = export_project_report_docx(report, run_id=run.id)
        session.add(
            ProjectArtifact(
                run_id=run.id,
                artifact_type="docx",
                file_path=str(docx_path),
            )
        )
        await session.commit()
    except Exception as exc:
        run.status = "error"
        run.error_message = str(exc)
        run.finished_at = _now()
        await session.commit()
        raise

    refreshed = await get_project_planner_run_model(session, run.id)
    return _detail(refreshed)


async def list_project_planner_runs(session: AsyncSession) -> list[ProjectPlannerRunSummary]:
    runs = (
        (
            await session.execute(
                select(ProjectPlannerRun)
                .options(
                    selectinload(ProjectPlannerRun.request),
                    selectinload(ProjectPlannerRun.artifacts),
                )
                .order_by(ProjectPlannerRun.id.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    return [_summary(run) for run in runs]


async def get_project_planner_run_model(
    session: AsyncSession,
    run_id: int,
) -> ProjectPlannerRun:
    run = (
        await session.execute(
            select(ProjectPlannerRun)
            .where(ProjectPlannerRun.id == run_id)
            .options(
                selectinload(ProjectPlannerRun.request),
                selectinload(ProjectPlannerRun.artifacts),
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Запуск project planner не найден.")
    return run


async def get_project_planner_run(
    session: AsyncSession,
    run_id: int,
) -> ProjectPlannerRunDetail:
    return _detail(await get_project_planner_run_model(session, run_id))


async def get_docx_path(session: AsyncSession, run_id: int) -> Path:
    run = await get_project_planner_run_model(session, run_id)
    artifact = next((item for item in run.artifacts if item.artifact_type == "docx"), None)
    if artifact is None:
        raise HTTPException(status_code=404, detail="DOCX для запуска не найден.")
    path = Path(artifact.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Файл DOCX отсутствует на диске.")
    return path
