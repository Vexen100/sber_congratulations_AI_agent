import { api, postJson } from "../api";
import type {
  ClarificationResponse,
  ProjectPlannerInput,
  ProjectPlannerRunDetail,
  ProjectPlannerRunResponse,
  ProjectPlannerRunSummary
} from "../types/projectPlanner";

export function clarifyProjectPlanner(input: ProjectPlannerInput): Promise<ClarificationResponse> {
  return postJson<ClarificationResponse>("/api/project-planner/clarifications", input);
}

export function createProjectPlannerRun(
  input: ProjectPlannerInput,
  generateWithAssumptions = true
): Promise<ProjectPlannerRunResponse> {
  return postJson<ProjectPlannerRunResponse>("/api/project-planner/runs", {
    input,
    generate_with_assumptions: generateWithAssumptions
  });
}

export function listProjectPlannerRuns(): Promise<ProjectPlannerRunSummary[]> {
  return api<ProjectPlannerRunSummary[]>("/api/project-planner/runs");
}

export function getProjectPlannerRun(runId: number): Promise<ProjectPlannerRunDetail> {
  return api<ProjectPlannerRunDetail>(`/api/project-planner/runs/${runId}`);
}
