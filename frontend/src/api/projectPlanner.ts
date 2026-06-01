import { ApiError, api, postJson } from "../api";
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

function filenameFromContentDisposition(value: string | null, runId: number | string): string {
  if (!value) return `project-planner-run-${runId}.docx`;

  const encoded = value.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  if (encoded) {
    try {
      return decodeURIComponent(encoded.replace(/^"|"$/g, ""));
    } catch {
      return encoded.replace(/^"|"$/g, "");
    }
  }

  return value.match(/filename="?([^";]+)"?/i)?.[1] ?? `project-planner-run-${runId}.docx`;
}

export async function downloadProjectPlannerDocx(runId: number | string): Promise<void> {
  const response = await fetch(`/api/project-planner/runs/${runId}/docx`);
  if (!response.ok) {
    throw new ApiError(`Не удалось скачать DOCX: HTTP ${response.status}`, response.status);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filenameFromContentDisposition(response.headers.get("Content-Disposition"), runId);
  link.style.display = "none";
  document.body.appendChild(link);
  try {
    link.click();
  } finally {
    link.remove();
    URL.revokeObjectURL(url);
  }
}
