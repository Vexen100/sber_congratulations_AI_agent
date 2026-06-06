from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models import utcnow


class ProjectRequest(Base):
    __tablename__ = "project_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    idea: Mapped[str] = mapped_column(Text)
    deadline: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    budget: Mapped[float | None] = mapped_column(nullable=True)
    geography: Mapped[str | None] = mapped_column(String(500), nullable=True)
    stakeholders: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_resources: Mapped[str | None] = mapped_column(Text, nullable=True)
    technology_constraints: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_accents: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    runs: Mapped[list["ProjectPlannerRun"]] = relationship(back_populates="request")


class ProjectPlannerRun(Base):
    __tablename__ = "project_planner_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("project_requests.id"))
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    warnings_json: Mapped[list] = mapped_column(JSON, default=list)
    assumptions_json: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(50), default="running")
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    request: Mapped[ProjectRequest] = relationship(back_populates="runs")
    artifacts: Mapped[list["ProjectArtifact"]] = relationship(back_populates="run")


class ProjectArtifact(Base):
    __tablename__ = "project_artifacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("project_planner_runs.id"))
    artifact_type: Mapped[str] = mapped_column(String(50))
    file_path: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    run: Mapped[ProjectPlannerRun] = relationship(back_populates="artifacts")
