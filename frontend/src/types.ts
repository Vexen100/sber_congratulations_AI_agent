export type Client = {
  id: number;
  first_name: string;
  middle_name: string | null;
  last_name: string;
  company_name: string | null;
  official_company_name: string | null;
  position: string | null;
  profession: string | null;
  inn: string | null;
  ogrn: string | null;
  kpp: string | null;
  ceo_name: string | null;
  okved_code: string | null;
  okved_name: string | null;
  company_status: string | null;
  company_address: string | null;
  company_site: string | null;
  source_url: string | null;
  enrichment_status: string;
  enrichment_error: string | null;
  enriched_at: string | null;
  email: string | null;
  phone: string | null;
  preferred_channel: string;
  birth_date: string | null;
  preferences: Record<string, unknown>;
  last_interaction_summary: string | null;
  is_demo: boolean;
  created_at: string | null;
};

export type EventItem = {
  id: number;
  client_id: number | null;
  event_type: string;
  event_date: string | null;
  title: string;
  metadata: Record<string, unknown>;
  created_at: string | null;
  client?: Client | null;
};

export type Feedback = {
  id: number;
  greeting_id: number;
  outcome: string;
  score: number | null;
  notes: string | null;
  training_verdict: string | null;
  created_at: string | null;
};

export type Delivery = {
  id: number;
  greeting_id: number;
  channel: string;
  recipient: string;
  status: string;
  provider_message: string | null;
  sent_at: string | null;
  idempotency_key: string;
  greeting?: Greeting | null;
};

export type Greeting = {
  id: number;
  event_id: number;
  client_id: number | null;
  agent_run_id: number | null;
  tone: string;
  subject: string;
  body: string;
  image_path: string | null;
  image_url: string | null;
  generation_source: string | null;
  status: string;
  created_at: string | null;
  event?: EventItem | null;
  client?: Client | null;
  deliveries?: Delivery[];
  feedback_entries?: Feedback[];
};

export type AgentRun = {
  id: number;
  triggered_by: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  lookahead_days: number;
  llm_mode: string;
  image_mode: string;
  scanned_events: number;
  generated_greetings: number;
  sent_deliveries: number;
  skipped_existing: number;
  errors: number;
  notes: string | null;
};

export type DashboardData = {
  clients_count: number;
  enriched_clients_count: number;
  events_count: number;
  greetings_count: number;
  deliveries_count: number;
  feedback_count: number;
  greetings_with_training_verdict: number;
  sent_greetings_count: number;
  delivery_errors_count: number;
  greetings_with_feedback_count: number;
  feedback_avg_score: number | null;
  runs_with_issues_count: number;
  delivery_success_rate: number;
  feedback_coverage_rate: number;
  last_runs: AgentRun[];
};

export type ClientsData = {
  clients: Client[];
  company_enrichment_provider: string;
};

export type EventsData = {
  events: EventItem[];
  clients: Client[];
};

export type GreetingsData = {
  greetings: Greeting[];
};

export type DeliveriesData = {
  deliveries: Delivery[];
};

export type RunsData = {
  runs: AgentRun[];
  total_runs: number;
  status_totals: Record<"success" | "partial" | "error" | "running", number>;
  autonomy: {
    enabled: boolean;
    next_run_at: string | null;
  };
};

export type RunDetailData = {
  run: AgentRun;
  greetings: Greeting[];
  actual_deliveries: number;
  actual_sent: number;
  greetings_with_feedback: number;
  greetings_with_training_verdict: number;
};
