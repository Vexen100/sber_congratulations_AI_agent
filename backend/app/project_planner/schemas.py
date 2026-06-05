from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

EffortLevel = Literal["низкая", "средняя", "высокая", "очень высокая"]
RunStatus = Literal["running", "success", "fallback", "error"]
ArtifactType = Literal["docx", "pptx", "defense_script"]


class ProjectPlannerInput(BaseModel):
    idea: str = Field(default="", max_length=4000)
    deadline: dt.date | None = None
    budget: float | None = Field(default=None, ge=0)
    geography: str | None = Field(default=None, max_length=500)
    stakeholders: str | None = Field(default=None, max_length=2000)
    current_resources: str | None = Field(default=None, max_length=2000)
    technology_constraints: str | None = Field(default=None, max_length=2000)
    project_accents: str | None = Field(
        default=None,
        max_length=3000,
        validation_alias=AliasChoices("project_accents", "additional_context"),
        serialization_alias="project_accents",
    )
    questions_asked_count: int = Field(default=0, ge=0, le=100)

    model_config = ConfigDict(populate_by_name=True)


class SourceInput(BaseModel):
    idea: str
    deadline: dt.date | None
    budget: float | None
    geography: str | None
    stakeholders: str | None
    current_resources: str | None
    technology_constraints: str | None
    project_accents: str | None


class ClarificationQuestion(BaseModel):
    field: str
    question: str
    reason: str


class ClarificationResponse(BaseModel):
    questions: list[ClarificationQuestion]
    can_generate_with_assumptions: bool
    default_limit: int
    max_limit: int


class ProjectPassport(BaseModel):
    title: str
    goal: str
    tasks: list[str]
    target_audience: str
    success_criteria: list[str]
    relevance_for_ural_bank: str
    risks: list[str]
    assumptions: list[str]


class Milestone(BaseModel):
    title: str
    due_date: dt.date
    description: str


class RoadmapPhase(BaseModel):
    name: str
    start_date: dt.date
    end_date: dt.date
    milestones: list[Milestone]


class GanttRow(BaseModel):
    phase: str
    period: str
    timeline: str


class FinancialItem(BaseModel):
    category: str
    amount: float
    comment: str


class ResourcePlan(BaseModel):
    financial_items: list[FinancialItem]
    financial_total: float
    material_resources: list[str]
    information_resources: list[str]


class ProjectRole(BaseModel):
    title: str
    count: int = Field(ge=1)
    competencies: list[str]
    assignment_comment: str


class RaciItem(BaseModel):
    activity: str
    responsible: str
    accountable: str
    consulted: list[str]
    informed: list[str]


class ConceptOption(BaseModel):
    name: str
    key_idea: str
    scenario_steps: list[str]
    advantages: list[str]
    disadvantages: list[str]
    estimated_cost: float
    effort_level: EffortLevel
    effort_factors: list[str]
    differences: str


class RecommendedConcept(BaseModel):
    concept_name: str
    rationale: str
    risks: list[str]


class PresentationSlide(BaseModel):
    title: str
    bullets: list[str]


class ProjectReport(BaseModel):
    source_input: SourceInput
    passport: ProjectPassport
    roadmap: list[RoadmapPhase]
    gantt: list[GanttRow]
    resources: ResourcePlan
    team: list[ProjectRole]
    raci: list[RaciItem]
    concepts: list[ConceptOption]
    recommended_concept: RecommendedConcept
    warnings: list[str]
    assumptions: list[str]
    presentation_outline: list[PresentationSlide] = Field(default_factory=list)
    defense_script: str | None = None


class ProjectPlannerRunCreate(BaseModel):
    input: ProjectPlannerInput
    generate_with_assumptions: bool = True


class ProjectPlannerRunSummary(BaseModel):
    id: int
    request_id: int
    status: str
    model_name: str | None
    created_at: dt.datetime
    finished_at: dt.datetime | None
    title: str
    deadline: dt.date | None
    warnings_count: int
    assumptions_count: int
    has_docx: bool


class ProjectArtifactOut(BaseModel):
    id: int
    artifact_type: str
    created_at: dt.datetime


class ProjectPlannerRunDetail(ProjectPlannerRunSummary):
    input: ProjectPlannerInput
    report: ProjectReport | None
    warnings: list[str]
    assumptions: list[str]
    artifacts: list[ProjectArtifactOut]


class ProjectPlannerRunResponse(BaseModel):
    run: ProjectPlannerRunDetail


class ReferencePackMetadata(BaseModel):
    pack_name: str
    pack_version: str
    source_name: str
    source_date: str
    confidence: str
    regions: list[str]
    keywords: list[str]
    project_types: list[str]
    facts_count: int
    constraints_count: int
    concept_prefer_count: int
    concept_avoid_count: int
    resource_notes_count: int
    has_budget_notes: bool


class ReferencePackListResponse(BaseModel):
    items: list[ReferencePackMetadata]
    count: int


class ReferencePackSelectionPreviewResponse(ReferencePackListResponse):
    reference_context_length: int
