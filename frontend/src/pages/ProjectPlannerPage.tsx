import { useEffect, useState, type FormEvent, type MouseEvent } from "react";

import {
  clarifyProjectPlanner,
  createProjectPlannerRun,
  downloadProjectPlannerDocx,
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

function textValue(value: string | null | undefined): string {
  const text = (value ?? "").trim();
  return text || "не указано";
}

function dateValue(value: string | null | undefined): string {
  return value ? formatDate(value) : "не указано";
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

function KeyValueTable({ rows }: { rows: Array<{ label: string; value: string }> }) {
  return (
    <div className="table-responsive">
      <table className="table table-sm table-clean align-middle">
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <th className="text-nowrap">{row.label}</th>
              <td>{row.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ReportPreview({ report }: { report: ProjectReport }) {
  return (
    <div className="planner-preview">
      <div className="surface-card mb-3">
        <div className="card-header">Исходные данные</div>
        <div className="card-body">
          <KeyValueTable
            rows={[
              { label: "Идея", value: textValue(report.source_input.idea) },
              { label: "Дедлайн", value: dateValue(report.source_input.deadline) },
              { label: "Бюджет", value: currency(report.source_input.budget) },
              { label: "География", value: textValue(report.source_input.geography) },
              { label: "Стейкхолдеры", value: textValue(report.source_input.stakeholders) },
              { label: "Текущие ресурсы", value: textValue(report.source_input.current_resources) },
              {
                label: "Технологические ограничения",
                value: textValue(report.source_input.technology_constraints)
              },
              { label: "Акценты проекта", value: textValue(report.source_input.project_accents) }
            ]}
          />
        </div>
      </div>

      <div className="surface-card mb-3">
        <div className="card-header">Паспорт проекта</div>
        <div className="card-body">
          <h3 className="h5">{report.passport.title}</h3>
          <p>{report.passport.goal}</p>
          <KeyValueTable
            rows={[
              { label: "Целевая аудитория", value: report.passport.target_audience },
              { label: "Актуальность", value: report.passport.relevance_for_ural_bank }
            ]}
          />
          <div className="row g-3">
            <div className="col-12 col-lg-6">
              <div className="section-title">Задачи</div>
              <BulletList items={report.passport.tasks} />
            </div>
            <div className="col-12 col-lg-6">
              <div className="section-title">Критерии успеха</div>
              <BulletList items={report.passport.success_criteria} />
            </div>
            <div className="col-12 col-lg-6">
              <div className="section-title">Риски</div>
              <BulletList items={report.passport.risks} />
            </div>
            <div className="col-12 col-lg-6">
              <div className="section-title">Допущения паспорта</div>
              <BulletList items={report.passport.assumptions} />
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
                  <td>
                    <ul className="planner-list">
                      {phase.milestones.map((item) => (
                        <li key={`${phase.name}:${item.title}`}>
                          <b>{item.title}</b> · {formatDate(item.due_date)}
                          <div className="text-muted small">{item.description}</div>
                        </li>
                      ))}
                    </ul>
                  </td>
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
              <div className="table-responsive mb-3">
                <table className="table table-sm table-clean align-middle">
                  <thead>
                    <tr>
                      <th>Статья</th>
                      <th>Сумма</th>
                      <th>Комментарий</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.resources.financial_items.map((item) => (
                      <tr key={item.category}>
                        <td>{item.category}</td>
                        <td>{currency(item.amount)}</td>
                        <td>{item.comment}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="section-title">Материально-технические ресурсы</div>
              <BulletList items={report.resources.material_resources} />
              <div className="section-title mt-3">Информационные ресурсы</div>
              <BulletList items={report.resources.information_resources} />
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
                  <div>{role.assignment_comment}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="surface-card mb-3">
        <div className="card-header">RACI</div>
        <div className="card-body table-responsive">
          <table className="table table-sm table-clean align-middle">
            <thead>
              <tr>
                <th>Активность</th>
                <th>R</th>
                <th>A</th>
                <th>C</th>
                <th>I</th>
              </tr>
            </thead>
            <tbody>
              {report.raci.map((item) => (
                <tr key={item.activity}>
                  <td className="fw-semibold">{item.activity}</td>
                  <td>{item.responsible}</td>
                  <td>{item.accountable}</td>
                  <td>{item.consulted.join(", ")}</td>
                  <td>{item.informed.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
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
                  <div className="section-title mt-3">Сценарий</div>
                  <BulletList items={concept.scenario_steps} />
                  <div className="section-title mt-3">Преимущества</div>
                  <BulletList items={concept.advantages} />
                  <div className="section-title mt-3">Недостатки</div>
                  <BulletList items={concept.disadvantages} />
                  <div className="section-title mt-3">Факторы трудоёмкости</div>
                  <BulletList items={concept.effort_factors} />
                  <div className="text-muted small mt-3">{concept.differences}</div>
                </div>
              </div>
            ))}
          </div>
          <div className="planner-recommendation mt-3">
            <b>Рекомендация:</b> {report.recommended_concept.concept_name}.{" "}
            {report.recommended_concept.rationale}
            <div className="section-title mt-3">Риски выбранной концепции</div>
            <BulletList items={report.recommended_concept.risks} />
          </div>
        </div>
      </div>

      {report.presentation_outline.length ? (
        <div className="surface-card mb-3">
          <div className="card-header">Outline презентации</div>
          <div className="card-body">
            <div className="row g-3">
              {report.presentation_outline.map((slide) => (
                <div className="col-12 col-lg-6" key={slide.title}>
                  <div className="planner-concept h-100">
                    <h4 className="h6">{slide.title}</h4>
                    <BulletList items={slide.bullets} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : null}

      {report.defense_script ? (
        <div className="surface-card mb-3">
          <div className="card-header">Сценарий защиты</div>
          <div className="card-body">
            <p className="mb-0">{report.defense_script}</p>
          </div>
        </div>
      ) : null}
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
  onSelect,
  onDownload,
  busy
}: {
  runs: ProjectPlannerRunSummary[];
  onSelect: (run: ProjectPlannerRunSummary) => void;
  onDownload: (event: MouseEvent<HTMLButtonElement>, runId: number) => void;
  busy: string | null;
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
                    <button
                      className="btn btn-sm btn-outline-success"
                      disabled={busy === `docx-${run.id}`}
                      type="button"
                      onClick={(event) => onDownload(event, run.id)}
                    >
                      {busy === `docx-${run.id}` ? "Скачиваю..." : "Скачать"}
                    </button>
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
  const [generateWithAssumptions, setGenerateWithAssumptions] = useState(true);

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
      const response = await createProjectPlannerRun(input, generateWithAssumptions);
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

  async function handleDownloadDocx(event: MouseEvent<HTMLButtonElement>, runId: number) {
    event.preventDefault();
    event.stopPropagation();
    setBusy(`docx-${runId}`);
    try {
      await downloadProjectPlannerDocx(runId);
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

                <div className="form-check form-switch">
                  <input
                    className="form-check-input"
                    id="planner-generate-with-assumptions"
                    type="checkbox"
                    checked={generateWithAssumptions}
                    onChange={(event) => setGenerateWithAssumptions(event.target.checked)}
                  />
                  <label className="form-check-label" htmlFor="planner-generate-with-assumptions">
                    Генерировать с допущениями
                  </label>
                  <div className="form-text">
                    Если выключить, генерация остановится при нехватке исходных данных.
                  </div>
                </div>

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
                <button
                  className="btn btn-sm btn-success"
                  disabled={busy === `docx-${selectedRun.id}`}
                  type="button"
                  onClick={(event) => handleDownloadDocx(event, selectedRun.id)}
                >
                  {busy === `docx-${selectedRun.id}` ? "Скачиваю..." : "Скачать DOCX"}
                </button>
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
        <HistoryTable runs={runs} onSelect={selectFromHistory} onDownload={handleDownloadDocx} busy={busy} />
        {busy?.startsWith("run-") ? <div className="text-muted mt-2">Загружаю выбранный запуск...</div> : null}
      </div>
    </>
  );
}
