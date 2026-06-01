import { useEffect, useState, type FormEvent } from "react";

import {
  clarifyProjectPlanner,
  createProjectPlannerRun,
  getProjectPlannerRun,
  listProjectPlannerRuns
} from "../api/projectPlanner";
import type {
  ClarificationQuestion,
  ProjectPlannerInput,
  ProjectPlannerRunDetail,
  ProjectPlannerRunSummary,
  ProjectReport
} from "../types/projectPlanner";
import { formatDate, formatDateTime } from "../utils";

type PlannerFlash = {
  type: "success" | "danger";
  text: string;
} | null;

const emptyInput: ProjectPlannerInput = {
  idea: "",
  deadline: null,
  budget: null,
  geography: "",
  stakeholders: "",
  current_resources: "",
  technology_constraints: "",
  project_accents: "",
  questions_asked_count: 0
};

function asNullable(value: string): string | null {
  const text = value.trim();
  return text ? text : null;
}

function currency(value: number | null | undefined): string {
  if (value === null || value === undefined) return "не указано";
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(value);
}

function BulletList({ items }: { items: string[] }) {
  if (!items.length) return <div className="text-muted">Нет данных</div>;
  return (
    <ul className="planner-list">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

function ReportPreview({ report }: { report: ProjectReport }) {
  return (
    <div className="planner-preview">
      <div className="surface-card mb-3">
        <div className="card-header">Паспорт проекта</div>
        <div className="card-body">
          <h3 className="h5">{report.passport.title}</h3>
          <p>{report.passport.goal}</p>
          <div className="row g-3">
            <div className="col-12 col-lg-6">
              <div className="section-title">Задачи</div>
              <BulletList items={report.passport.tasks} />
            </div>
            <div className="col-12 col-lg-6">
              <div className="section-title">Критерии успеха</div>
              <BulletList items={report.passport.success_criteria} />
            </div>
          </div>
        </div>
      </div>

      <div className="surface-card mb-3">
        <div className="card-header">Дорожная карта</div>
        <div className="card-body table-responsive">
          <table className="table table-sm table-clean align-middle">
            <thead>
              <tr>
                <th>Фаза</th>
                <th>Период</th>
                <th>Контрольные точки</th>
              </tr>
            </thead>
            <tbody>
              {report.roadmap.map((phase) => (
                <tr key={phase.name}>
                  <td className="fw-semibold">{phase.name}</td>
                  <td>
                    {formatDate(phase.start_date)} - {formatDate(phase.end_date)}
                  </td>
                  <td>{phase.milestones.map((item) => item.title).join("; ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="planner-gantt">
            {report.gantt.map((row) => (
              <div className="planner-gantt-row" key={row.phase}>
                <span>{row.phase}</span>
                <code>{row.timeline}</code>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="row g-3 mb-3">
        <div className="col-12 col-xl-6">
          <div className="surface-card h-100">
            <div className="card-header">Ресурсы</div>
            <div className="card-body">
              <div className="metric-value planner-money">{currency(report.resources.financial_total)}</div>
              <div className="text-muted mb-3">предварительная оценка бюджета</div>
              <BulletList items={report.resources.material_resources} />
            </div>
          </div>
        </div>
        <div className="col-12 col-xl-6">
          <div className="surface-card h-100">
            <div className="card-header">Команда</div>
            <div className="card-body">
              {report.team.map((role) => (
                <div className="planner-role" key={role.title}>
                  <b>{role.title}</b> · {role.count} чел.
                  <div className="text-muted small">{role.competencies.join(", ")}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="surface-card mb-3">
        <div className="card-header">Концепции</div>
        <div className="card-body">
          <div className="row g-3">
            {report.concepts.map((concept) => (
              <div className="col-12 col-xl-4" key={concept.name}>
                <div className="planner-concept">
                  <h4 className="h6">{concept.name}</h4>
                  <p>{concept.key_idea}</p>
                  <div className="text-muted small">
                    Стоимость: {currency(concept.estimated_cost)} · трудоёмкость: {concept.effort_level}
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div className="planner-recommendation mt-3">
            <b>Рекомендация:</b> {report.recommended_concept.concept_name}.{" "}
            {report.recommended_concept.rationale}
          </div>
        </div>
      </div>
    </div>
  );
}

function ClarificationsBlock({
  questions,
  canGenerate
}: {
  questions: ClarificationQuestion[];
  canGenerate: boolean;
}) {
  return (
    <div className="surface-panel">
      <div className="section-title">Уточняющие вопросы</div>
      {questions.length ? (
        <div className="d-grid gap-2 mt-3">
          {questions.map((item) => (
            <div className="planner-question" key={`${item.field}:${item.question}`}>
              <b>{item.question}</b>
              <div className="text-muted small">{item.reason}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-muted mt-2">Критичных уточнений нет.</div>
      )}
      {canGenerate ? (
        <div className="alert alert-warning mt-3 mb-0">
          Можно сгенерировать отчёт с допущениями. Неполные данные будут явно отражены в разделе assumptions.
        </div>
      ) : null}
    </div>
  );
}

function HistoryTable({
  runs,
  onSelect
}: {
  runs: ProjectPlannerRunSummary[];
  onSelect: (run: ProjectPlannerRunSummary) => void;
}) {
  return (
    <div className="surface-card">
      <div className="card-header">История запусков</div>
      <div className="card-body table-responsive">
        <table className="table table-sm table-clean align-middle">
          <thead>
            <tr>
              <th>ID</th>
              <th>Проект</th>
              <th>Статус</th>
              <th>Дата</th>
              <th>DOCX</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id}>
                <td className="fw-semibold">#{run.id}</td>
                <td>
                  <button className="btn btn-link p-0 planner-link" onClick={() => onSelect(run)}>
                    {run.title}
                  </button>
                  <div className="text-muted small">модель: {run.model_name ?? "—"}</div>
                </td>
                <td>
                  <span className="badge text-bg-light">{run.status}</span>
                </td>
                <td>{formatDateTime(run.created_at)}</td>
                <td>
                  {run.has_docx ? (
                    <a className="btn btn-sm btn-outline-success" href={`/api/project-planner/runs/${run.id}/docx`}>
                      Скачать
                    </a>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
            {runs.length === 0 ? (
              <tr>
                <td colSpan={5} className="empty-state">
                  Запусков пока нет.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function ProjectPlannerPage() {
  const [input, setInput] = useState<ProjectPlannerInput>(emptyInput);
  const [questions, setQuestions] = useState<ClarificationQuestion[]>([]);
  const [canGenerate, setCanGenerate] = useState(false);
  const [selectedRun, setSelectedRun] = useState<ProjectPlannerRunDetail | null>(null);
  const [runs, setRuns] = useState<ProjectPlannerRunSummary[]>([]);
  const [flash, setFlash] = useState<PlannerFlash>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function refreshHistory() {
    setRuns(await listProjectPlannerRuns());
  }

  useEffect(() => {
    refreshHistory().catch((error: unknown) => {
      setFlash({ type: "danger", text: error instanceof Error ? error.message : String(error) });
    });
  }, []);

  function updateField<K extends keyof ProjectPlannerInput>(field: K, value: ProjectPlannerInput[K]) {
    setInput((current) => ({ ...current, [field]: value }));
  }

  async function clarify() {
    setBusy("clarify");
    try {
      const response = await clarifyProjectPlanner(input);
      setQuestions(response.questions);
      setCanGenerate(response.can_generate_with_assumptions);
      setInput((current) => ({
        ...current,
        questions_asked_count: Math.min(
          response.max_limit,
          current.questions_asked_count + response.questions.length
        )
      }));
      setFlash({ type: "success", text: "Уточняющие вопросы обновлены." });
    } catch (error) {
      setFlash({ type: "danger", text: error instanceof Error ? error.message : String(error) });
    } finally {
      setBusy(null);
    }
  }

  async function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy("generate");
    try {
      const response = await createProjectPlannerRun(input);
      setSelectedRun(response.run);
      setQuestions([]);
      setCanGenerate(false);
      await refreshHistory();
      setFlash({ type: "success", text: "Проектный отчёт сгенерирован." });
    } catch (error) {
      setFlash({ type: "danger", text: error instanceof Error ? error.message : String(error) });
    } finally {
      setBusy(null);
    }
  }

  async function selectFromHistory(run: ProjectPlannerRunSummary) {
    setBusy(`run-${run.id}`);
    try {
      const detail = await getProjectPlannerRun(run.id);
      setSelectedRun(detail);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (error) {
      setFlash({ type: "danger", text: error instanceof Error ? error.message : String(error) });
    } finally {
      setBusy(null);
    }
  }

  const report = selectedRun?.report ?? null;

  return (
    <>
      <div className="d-flex align-items-center justify-content-between mb-3">
        <div className="page-intro">
          <h2 className="mb-1">Планировщик проектов</h2>
          <div className="text-muted">Форма → уточнения → ProjectReport → DOCX.</div>
        </div>
      </div>
      {flash ? <div className={`alert alert-${flash.type}`}>{flash.text}</div> : null}

      <div className="row g-4">
        <div className="col-12 col-xl-5">
          <div className="surface-card">
            <div className="card-header">Исходные данные</div>
            <div className="card-body">
              <form className="planner-form" onSubmit={generate}>
                <label className="form-label">Суть идеи проекта</label>
                <textarea
                  className="form-control"
                  rows={5}
                  value={input.idea}
                  onChange={(event) => updateField("idea", event.target.value)}
                  placeholder="Например: провести фестиваль талантов в Уральском банке до 12 ноября"
                />

                <div className="row g-2">
                  <div className="col-12 col-md-6">
                    <label className="form-label">Желаемая конечная дата</label>
                    <input
                      className="form-control"
                      type="date"
                      value={input.deadline ?? ""}
                      onChange={(event) => updateField("deadline", asNullable(event.target.value))}
                    />
                  </div>
                  <div className="col-12 col-md-6">
                    <label className="form-label">Бюджет</label>
                    <input
                      className="form-control"
                      type="number"
                      min={0}
                      value={input.budget ?? ""}
                      onChange={(event) =>
                        updateField("budget", event.target.value ? Number(event.target.value) : null)
                      }
                    />
                  </div>
                </div>

                <label className="form-label">География</label>
                <input
                  className="form-control"
                  value={input.geography ?? ""}
                  onChange={(event) => updateField("geography", event.target.value)}
                  placeholder="Свердловская область, ХМАО, ЯНАО..."
                />

                <label className="form-label">Стейкхолдеры</label>
                <textarea
                  className="form-control"
                  rows={2}
                  value={input.stakeholders ?? ""}
                  onChange={(event) => updateField("stakeholders", event.target.value)}
                />

                <label className="form-label">Текущие ресурсы</label>
                <textarea
                  className="form-control"
                  rows={2}
                  value={input.current_resources ?? ""}
                  onChange={(event) => updateField("current_resources", event.target.value)}
                />

                <label className="form-label">Технологические ограничения</label>
                <textarea
                  className="form-control"
                  rows={2}
                  value={input.technology_constraints ?? ""}
                  onChange={(event) => updateField("technology_constraints", event.target.value)}
                />

                <label className="form-label">Акценты проекта / дополнительный контекст</label>
                <textarea
                  className="form-control"
                  rows={3}
                  value={input.project_accents ?? ""}
                  onChange={(event) => updateField("project_accents", event.target.value)}
                  placeholder="Например: учесть фестиваль 2023 года и 185-летие Сбера"
                />

                <div className="d-flex gap-2 flex-wrap mt-3">
                  <button
                    type="button"
                    className="btn btn-outline-success"
                    disabled={busy === "clarify" || busy === "generate"}
                    onClick={clarify}
                  >
                    {busy === "clarify" ? "Проверяю..." : "Получить вопросы"}
                  </button>
                  <button className="btn btn-success" disabled={busy === "generate"}>
                    {busy === "generate" ? "Генерирую..." : "Сгенерировать отчёт"}
                  </button>
                </div>
              </form>
            </div>
          </div>

          <div className="mt-4">
            <ClarificationsBlock questions={questions} canGenerate={canGenerate} />
          </div>
        </div>

        <div className="col-12 col-xl-7">
          {selectedRun ? (
            <div className="planner-result-actions mb-3">
              <span className="badge text-bg-light">Запуск #{selectedRun.id}</span>
              <span className="badge text-bg-light">Статус: {selectedRun.status}</span>
              {selectedRun.has_docx ? (
                <a className="btn btn-sm btn-success" href={`/api/project-planner/runs/${selectedRun.id}/docx`}>
                  Скачать DOCX
                </a>
              ) : null}
            </div>
          ) : null}

          {selectedRun?.warnings.length ? (
            <div className="alert alert-warning">
              <b>Warnings:</b> {selectedRun.warnings.join(" ")}
            </div>
          ) : null}
          {selectedRun?.assumptions.length ? (
            <div className="alert alert-info">
              <b>Assumptions:</b> {selectedRun.assumptions.join(" ")}
            </div>
          ) : null}

          {report ? (
            <ReportPreview report={report} />
          ) : (
            <div className="surface-panel empty-state">Preview появится после генерации или выбора запуска.</div>
          )}
        </div>
      </div>

      <div className="mt-4">
        <HistoryTable runs={runs} onSelect={selectFromHistory} />
        {busy?.startsWith("run-") ? <div className="text-muted mt-2">Загружаю выбранный запуск...</div> : null}
      </div>
    </>
  );
}
