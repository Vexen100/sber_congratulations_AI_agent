export type ProjectPlannerInput = {
  idea: string;
  deadline: string | null;
  budget: number | null;
  geography: string | null;
  stakeholders: string | null;
  current_resources: string | null;
  technology_constraints: string | null;
  project_accents: string | null;
  questions_asked_count: number;
};

export type ProjectSourceInput = Omit<ProjectPlannerInput, "questions_asked_count">;

export type ClarificationQuestion = {
  field: string;
  question: string;
  reason: string;
};

export type ClarificationResponse = {
  questions: ClarificationQuestion[];
  can_generate_with_assumptions: boolean;
  default_limit: number;
  max_limit: number;
};

export type ProjectReport = {
  source_input: ProjectSourceInput;
  passport: {
    title: string;
    goal: string;
    tasks: string[];
    target_audience: string;
    success_criteria: string[];
    relevance_for_ural_bank: string;
    risks: string[];
    assumptions: string[];
  };
  roadmap: Array<{
    name: string;
    start_date: string;
    end_date: string;
    milestones: Array<{ title: string; due_date: string; description: string }>;
  }>;
  gantt: Array<{ phase: string; period: string; timeline: string }>;
  resources: {
    financial_items: Array<{ category: string; amount: number; comment: string }>;
    financial_total: number;
    material_resources: string[];
    information_resources: string[];
  };
  team: Array<{
    title: string;
    count: number;
    competencies: string[];
    assignment_comment: string;
  }>;
  raci: Array<{
    activity: string;
    responsible: string;
    accountable: string;
    consulted: string[];
    informed: string[];
  }>;
  concepts: Array<{
    name: string;
    key_idea: string;
    scenario_steps: string[];
    advantages: string[];
    disadvantages: string[];
    estimated_cost: number;
    effort_level: string;
    effort_factors: string[];
    differences: string;
  }>;
  recommended_concept: {
    concept_name: string;
    rationale: string;
    risks: string[];
  };
  warnings: string[];
  assumptions: string[];
  presentation_outline: Array<{ title: string; bullets: string[] }>;
  defense_script: string | null;
};

export type ProjectPlannerRunSummary = {
  id: number;
  request_id: number;
  status: string;
  model_name: string | null;
  created_at: string;
  finished_at: string | null;
  title: string;
  deadline: string | null;
  warnings_count: number;
  assumptions_count: number;
  has_docx: boolean;
};

export type ProjectPlannerRunDetail = ProjectPlannerRunSummary & {
  input: ProjectPlannerInput;
  report: ProjectReport | null;
  warnings: string[];
  assumptions: string[];
  artifacts: Array<{
    id: number;
    artifact_type: string;
    created_at: string;
  }>;
};

export type ProjectPlannerRunResponse = {
  run: ProjectPlannerRunDetail;
};
