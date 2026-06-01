import {
  useEffect,
  useState,
  type CSSProperties,
  type FormEvent,
  type MouseEvent,
  type ReactNode
} from "react";

import { api, postJson } from "./api";
import ProjectPlannerPage from "./pages/ProjectPlannerPage";
import type {
  AgentRun,
  Client,
  ClientsData,
  DashboardData,
  DeliveriesData,
  Delivery,
  EventItem,
  EventsData,
  Greeting,
  GreetingsData,
  RunDetailData,
  RunsData
} from "./types";
import {
  formatDate,
  formatDateTime,
  formatMskTime,
  percent,
  professionLabels,
  splitContactValues,
  statusBadgeClass,
  statusLabel
} from "./utils";

type Flash = {
  type: "success" | "danger";
  text: string;
} | null;

type PageState<T> =
  | { loading: true; data?: never; error?: never }
  | { loading: false; data: T; error?: never }
  | { loading: false; data?: never; error: string };

const navItems = [
  { href: "/", label: "Дашборд" },
  { href: "/clients", label: "Клиенты" },
  { href: "/events", label: "События" },
  { href: "/greetings", label: "Поздравления" },
  { href: "/deliveries", label: "Доставки" },
  { href: "/project-planner", label: "Планировщик проектов" },
  { href: "/runs", label: "Запуски агента" }
];

function usePageData<T>(key: string, load: () => Promise<T>): PageState<T> {
  const [state, setState] = useState<PageState<T>>({ loading: true });

  useEffect(() => {
    let cancelled = false;
    setState({ loading: true });
    load()
      .then((data) => {
        if (!cancelled) setState({ loading: false, data });
      })
      .catch((error: unknown) => {
        const message = error instanceof Error ? error.message : String(error);
        if (!cancelled) setState({ loading: false, error: message });
      });
    return () => {
      cancelled = true;
    };
  }, [key]);

  return state;
}

function LoadingState() {
  return <div className="surface-panel empty-state">Загружаю данные...</div>;
}

function ErrorState({ error }: { error: string }) {
  return <div className="alert alert-danger">Не удалось загрузить данные: {error}</div>;
}

function EmptyRow({ colSpan, children }: { colSpan: number; children: ReactNode }) {
  return (
    <tr>
      <td colSpan={colSpan} className="empty-state">
        {children}
      </td>
    </tr>
  );
}

function StatusBadge({ status }: { status: string }) {
  return <span className={`badge ${statusBadgeClass(status)}`}>{statusLabel(status)}</span>;
}

function MetricCard({
  label,
  value,
  hint,
  className = ""
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  className?: string;
}) {
  return (
    <div className={`surface-panel metric-card h-100 ${className}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      {hint ? <div className="metric-hint">{hint}</div> : null}
    </div>
  );
}

function Layout({
  path,
  flash,
  actionBusy,
  children,
  onNavigate,
  onRunAgent,
  onSeedDemo,
  onResetRuntime
}: {
  path: string;
  flash: Flash;
  actionBusy: string | null;
  children: ReactNode;
  onNavigate: (path: string) => void;
  onRunAgent: () => void;
  onSeedDemo: () => void;
  onResetRuntime: () => void;
}) {
  function handleClick(event: MouseEvent<HTMLDivElement>) {
    if (!event.isTrusted) return;
    if (event.defaultPrevented) return;
    if (event.button !== 0) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;

    const link = (event.target as Element).closest("a");
    if (!link) return;
    const href = link.getAttribute("href");
    const target = link.getAttribute("target");
    if (
      !href ||
      link.hasAttribute("download") ||
      link.hasAttribute("data-no-spa") ||
      link.hasAttribute("data-router-ignore") ||
      (target && target !== "_self") ||
      href.startsWith("mailto:") ||
      href.startsWith("tel:") ||
      href.startsWith("blob:") ||
      href.startsWith("data:") ||
      href.startsWith("/api/") ||
      href.startsWith("/data/") ||
      href.startsWith("/static/")
    ) {
      return;
    }

    const url = new URL(href, window.location.origin);
    if (url.origin !== window.location.origin) return;

    event.preventDefault();
    onNavigate(`${url.pathname}${url.search}${url.hash}`);
  }

  return (
    <div className="container-fluid layout-shell" onClick={handleClick}>
      <div className="row g-0">
        <aside className="col-12 col-lg-3 col-xl-2 p-3 p-lg-4 min-vh-100 sidebar-shell">
          <div className="d-grid gap-2 mb-4">
            <button
              className="btn btn-success quick-action w-100"
              disabled={actionBusy === "run"}
              onClick={onRunAgent}
            >
              {actionBusy === "run" ? "Запускаю..." : "Запустить агента"}
            </button>
            <button
              className="btn btn-outline-secondary quick-action w-100"
              disabled={actionBusy === "seed"}
              onClick={onSeedDemo}
            >
              {actionBusy === "seed" ? "Загружаю..." : "Загрузить данные"}
            </button>
            <button
              className="btn btn-outline-danger quick-action w-100"
              disabled={actionBusy === "reset"}
              onClick={onResetRuntime}
            >
              {actionBusy === "reset" ? "Очищаю..." : "Очистить среду"}
            </button>
          </div>

          <div className="sidebar-brand-wrap">
            <img
              className="sidebar-brand-logo"
              src="/static/vibe-team-logo.svg"
              alt="Vibe Team"
              loading="lazy"
            />
          </div>

          <div className="nav-stack">
            {navItems.map((item) => {
              const active =
                item.href === "/" ? path === "/" : path === item.href || path.startsWith(`${item.href}/`);
              return (
                <a key={item.href} className={`nav-chip ${active ? "active" : ""}`} href={item.href}>
                  <span>{item.label}</span>
                </a>
              );
            })}
          </div>

          <div className="mt-4">
            <div className="delivery-pill">Режим доставки: файловый outbox</div>
          </div>
        </aside>

        <main className="col-12 col-lg-9 col-xl-10 content-shell">
          <div className="topbar">
            <div />
          </div>
          {flash ? <div className={`alert alert-${flash.type}`}>{flash.text}</div> : null}
          {children}
        </main>
      </div>
    </div>
  );
}

function DashboardPage({ refreshKey }: { refreshKey: number }) {
  const state = usePageData<DashboardData>(`dashboard:${refreshKey}`, () =>
    api<DashboardData>("/api/ui/dashboard")
  );
  if (state.loading) return <LoadingState />;
  if (state.error) return <ErrorState error={state.error} />;
  if (!state.data) return <ErrorState error="Данные дашборда не получены." />;

  const data = state.data;
  const flowMetrics = [
    { label: "События", value: data.events_count, key: "events" },
    { label: "Поздравления", value: data.greetings_count, key: "greetings" },
    { label: "Доставки", value: data.deliveries_count, key: "deliveries" },
    { label: "Обратная связь", value: data.feedback_count, key: "feedback" }
  ].sort((a, b) => b.value - a.value);
  const maxFlow = Math.max(...flowMetrics.map((item) => item.value), 0);
  const enrichmentPercent = percent(data.enriched_clients_count, data.clients_count);

  return (
    <>
      <div className="hero-card mb-4">
        <div className="row g-4 align-items-center">
          <div className="col-12 col-xl-8">
            <div className="hero-badge mb-3">Центр управления</div>
            <h1 className="h2 mb-3">Быстрый просмотр данных</h1>
          </div>
          <div className="col-12 col-xl-4">
            <div className="kpi-strip justify-content-xl-end">
              <div className="kpi-pill">
                <span className="text-muted small">Клиенты</span>
                <b>{data.clients_count}</b>
              </div>
              <div className="kpi-pill">
                <span className="text-muted small">Отправлено&nbsp;/&nbsp;Ошибка</span>
                <div>
                  {data.sent_greetings_count}/{data.delivery_errors_count}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="row g-2">
        <div className="col-12 col-md-3">
          <div className="surface-panel metric-card combined-card">
            <div className="d-flex justify-content-between mb-3">
              <div>
                <div className="metric-label">Клиенты</div>
                <div className="metric-value">{data.clients_count}</div>
              </div>
              <div className="text-end">
                <div className="metric-label">Обогащено</div>
                <div className="metric-value">{data.enriched_clients_count}</div>
              </div>
            </div>
            <div className="enrichment-progress">
              <div className="progress-track">
                <div className="progress-fill" style={{ "--progress": `${enrichmentPercent}%` } as CSSProperties} />
              </div>
              <span className="progress-value">{enrichmentPercent}%</span>
            </div>
            <div className="css-gauge-wrapper">
              <div className="css-gauge-svg-container">
                <svg viewBox="0 0 200 110" className="css-gauge-svg">
                  <path
                    d="M 20 100 A 80 80 0 0 1 180 100"
                    fill="none"
                    stroke="var(--primary-soft)"
                    strokeWidth="20"
                    strokeLinecap="round"
                  />
                  <path
                    d="M 20 100 A 80 80 0 0 1 180 100"
                    fill="none"
                    stroke="var(--primary)"
                    strokeWidth="20"
                    strokeLinecap="round"
                    strokeDasharray="251.2"
                    strokeDashoffset={251.2 - 251.2 * (enrichmentPercent / 100)}
                    className="css-gauge-path"
                  />
                </svg>
                <div className="css-gauge-center">
                  <span className="gauge-value">{enrichmentPercent}%</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="metrics-flow-container">
          {flowMetrics.map((metric) => (
            <div className="flow-metric-card" data-metric={metric.key} key={metric.key}>
              <div className="flow-header">
                <span className="flow-label">{metric.label}</span>
                <span className="flow-value">{metric.value}</span>
              </div>
              <div className="flow-bar-container">
                <div
                  className="flow-bar"
                  style={{ "--bar-width": `${percent(metric.value, maxFlow)}%` } as CSSProperties}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="row g-4 mt-1">
        <div className="col-12 col-xl-8">
          <div className="surface-panel h-100">
            <div className="section-title">Воронка после запуска</div>
            <div className="section-subtitle mb-4">
              Показывает, как сгенерированные поздравления проходят через валидацию, доставку и обратную связь.
            </div>
            <div className="row g-3">
              <div className="col-12 col-md-6 col-xl-3">
                <MetricCard label="Сгенерировано" value={data.greetings_count} hint="Все поздравления, созданные агентом." />
              </div>
              <div className="col-12 col-md-6 col-xl-3">
                <MetricCard
                  label="Вердикт для дообучения"
                  value={data.greetings_with_training_verdict}
                  hint="Поздравления, по которым менеджер уже отметил принять/отклонить."
                />
              </div>
              <div className="col-12 col-md-6 col-xl-3">
                <MetricCard
                  label="Дошли до доставки"
                  value={data.sent_greetings_count}
                  hint="Поздравления, которые были успешно отправлены."
                />
              </div>
              <div className="col-12 col-md-6 col-xl-3">
                <MetricCard
                  label="Есть обратная связь"
                  value={data.greetings_with_feedback_count}
                  hint="Поздравления, по которым менеджер уже дал обратную связь."
                />
              </div>
            </div>
          </div>
        </div>
        <div className="col-12 col-xl-4">
          <div className="surface-panel h-100">
            <div className="section-title">Операционное здоровье</div>
            <div className="section-subtitle mb-4">Короткая сводка качества работы конвейера.</div>
            <div className="d-grid gap-3">
              <HealthLine label="Успешная доставка" value={`${data.delivery_success_rate}%`} />
              <HealthLine label="Покрытие обратной связи" value={`${data.feedback_coverage_rate}%`} />
              <HealthLine
                label="Ошибки доставки"
                value={data.delivery_errors_count}
                className={data.delivery_errors_count ? "text-danger" : ""}
              />
              <HealthLine
                label="Запуски с проблемами"
                value={data.runs_with_issues_count}
                className={data.runs_with_issues_count ? "text-warning" : ""}
              />
              <HealthLine label="Средняя оценка" value={data.feedback_avg_score ?? "нет данных"} />
            </div>
          </div>
        </div>
      </div>

      <div className="row g-4 mt-1">
        <div className="col-12 col-xl-7">
          <RunsTable runs={data.last_runs} compact />
        </div>
      </div>
    </>
  );
}

function HealthLine({ label, value, className = "" }: { label: string; value: ReactNode; className?: string }) {
  return (
    <div className="d-flex align-items-center justify-content-between">
      <span className="metric-label mb-0">{label}</span>
      <span className={`fw-semibold ${className}`}>{value}</span>
    </div>
  );
}

function ClientsPage({
  refreshKey,
  onChanged,
  setFlash
}: {
  refreshKey: number;
  onChanged: () => void;
  setFlash: (flash: Flash) => void;
}) {
  const state = usePageData<ClientsData>(`clients:${refreshKey}`, () =>
    api<ClientsData>("/api/ui/clients")
  );
  const [busy, setBusy] = useState<string | null>(null);

  async function runAction(name: string, path: string) {
    setBusy(name);
    try {
      const result = await postJson<{ message?: string }>(path);
      setFlash({ type: "success", text: result.message ?? "Действие выполнено." });
      onChanged();
    } catch (error) {
      setFlash({ type: "danger", text: error instanceof Error ? error.message : String(error) });
    } finally {
      setBusy(null);
    }
  }

  if (state.loading) return <LoadingState />;
  if (state.error) return <ErrorState error={state.error} />;
  if (!state.data) return <ErrorState error="Данные клиентов не получены." />;

  const { clients, company_enrichment_provider: provider } = state.data;
  const enrichedCount = clients.filter((client) => client.enrichment_status === "enriched").length;
  const demoCount = clients.filter((client) => client.is_demo).length;

  return (
    <>
      <div className="d-flex align-items-center justify-content-between mb-3">
        <div className="page-intro">
          <h2 className="mb-1">Клиенты</h2>
        </div>
        <div className="d-flex gap-2 flex-wrap">
          <button
            className="btn btn-outline-primary quick-action"
            disabled={busy === "import"}
            onClick={() => runAction("import", "/api/ui/clients/import-company-base")}
          >
            Импортировать базу компаний
          </button>
          <button
            className="btn btn-success quick-action"
            disabled={busy === "enrich"}
            onClick={() => runAction("enrich", "/api/ui/clients/enrich-missing")}
          >
            Обогатить профили компаний
          </button>
          {provider !== "demo" ? (
            <button
              className="btn btn-outline-success quick-action"
              disabled={busy === "refresh"}
              onClick={() => runAction("refresh", "/api/ui/clients/refresh-external")}
            >
              Актуализировать через внешний источник
            </button>
          ) : null}
        </div>
      </div>

      <div className="row g-4 mb-4">
        <div className="col-12 col-xl-8">
          <div className="surface-card form-panel h-100">
            <div className="card-header">Добавить клиента вручную</div>
            <div className="card-body">
              <ClientCreateForm
                onCreated={(message) => {
                  setFlash({ type: "success", text: message });
                  onChanged();
                }}
                onError={(message) => setFlash({ type: "danger", text: message })}
              />
            </div>
          </div>
        </div>
        <div className="col-12 col-xl-4">
          <div className="surface-panel">
            <div className="section-title">Качество данных</div>
            <div className="kpi-strip-container">
              <div className="kpi-pill">
                <span className="text-muted small">Всего клиентов</span>
                <b>{clients.length}</b>
              </div>
              <div className="kpi-pill">
                <span className="text-muted small">Обогащено</span>
                <b>{enrichedCount}</b>
              </div>
              <div className="kpi-pill">
                <span className="text-muted small">Демо-записи</span>
                <b>{demoCount}</b>
              </div>
            </div>
          </div>
        </div>
      </div>

      <ClientsTable
        clients={clients}
        provider={provider}
        onEnrich={(clientId) => runAction(`client-${clientId}`, `/api/ui/clients/${clientId}/enrich`)}
        busy={busy}
      />
    </>
  );
}

function ClientCreateForm({
  onCreated,
  onError
}: {
  onCreated: (message: string) => void;
  onError: (message: string) => void;
}) {
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const value = (name: string) => String(data.get(name) ?? "").trim();
    const nullable = (name: string) => {
      const text = value(name);
      return text ? text : null;
    };

    setBusy(true);
    try {
      await postJson<Client>("/api/clients", {
        first_name: value("first_name"),
        middle_name: value("middle_name"),
        last_name: value("last_name"),
        birth_date: nullable("birth_date"),
        profession: value("profession"),
        position: nullable("position"),
        company_name: nullable("company_name"),
        inn: nullable("inn"),
        email: nullable("email"),
        phone: nullable("phone"),
        preferred_channel: value("preferred_channel") || "email",
        preferences: {}
      });
      form.reset();
      onCreated("Клиент добавлен. Реальные письма отправляются только на ручные email.");
    } catch (error) {
      onError(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="row g-2" onSubmit={submit}>
      <div className="col-12">
        <h6 className="section-title text-muted mb-2 mt-1">Личные данные</h6>
      </div>
      <div className="col-12 col-md-3">
        <input className="form-control" name="first_name" placeholder="Имя" required minLength={2} maxLength={50} />
      </div>
      <div className="col-12 col-md-3">
        <input
          className="form-control"
          name="middle_name"
          placeholder="Отчество"
          title="Используется для уважительного обращения"
          required
          minLength={2}
          maxLength={50}
        />
      </div>
      <div className="col-12 col-md-3">
        <input className="form-control" name="last_name" placeholder="Фамилия" required minLength={2} maxLength={50} />
      </div>
      <div className="col-12 col-md-3">
        <input className="form-control" name="birth_date" placeholder="Дата рождения" type="date" />
      </div>

      <div className="col-12">
        <h6 className="section-title text-muted mb-2 mt-2">Работа и компания</h6>
      </div>
      <div className="col-12 col-md-3">
        <select className="form-select" name="profession" required title="Используется для профессиональных праздников">
          <option value="">Профессия</option>
          {Object.entries(professionLabels).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <div className="col-12 col-md-3">
        <input className="form-control" name="position" placeholder="Должность" />
      </div>
      <div className="col-12 col-md-3">
        <input className="form-control" name="company_name" placeholder="Компания" />
      </div>
      <div className="col-12 col-md-3">
        <input
          className="form-control"
          name="inn"
          placeholder="ИНН организации"
          title="Нужен для авто-обогащения профиля"
          minLength={10}
          maxLength={12}
        />
      </div>

      <div className="col-12">
        <h6 className="section-title text-muted mb-2 mt-2">Контакты и коммуникация</h6>
      </div>
      <div className="col-12 col-md-4">
        <input className="form-control" name="email" placeholder="Email" type="email" />
      </div>
      <div className="col-12 col-md-4">
        <input className="form-control" name="phone" placeholder="Телефон" />
      </div>
      <div className="col-12 col-md-4">
        <select className="form-select" name="preferred_channel" defaultValue="email">
          <option value="email">Email</option>
          <option value="sms">SMS</option>
          <option value="messenger">Мессенджер</option>
        </select>
      </div>
      <div className="col-12">
        <button className="btn btn-success quick-action px-4 mt-2" disabled={busy}>
          {busy ? "Добавляю..." : "Добавить клиента"}
        </button>
      </div>
    </form>
  );
}

function ClientsTable({
  clients,
  provider,
  onEnrich,
  busy
}: {
  clients: Client[];
  provider: string;
  onEnrich: (clientId: number) => void;
  busy: string | null;
}) {
  return (
    <div className="surface-card">
      <div className="card-header d-flex justify-content-between align-items-center">
        <span>Список клиентов</span>
        <span className="badge text-bg-secondary">Всего: {clients.length}</span>
      </div>
      <div className="card-body table-responsive">
        <table className="table table-sm align-middle table-clean">
          <thead>
            <tr>
              <th>ID</th>
              <th>ФИО</th>
              <th>Компания / Должность</th>
              <th>Обогащение</th>
              <th>Профиль</th>
              <th>Тип записи</th>
              <th>Контакт</th>
              <th>ДР</th>
              <th className="actions-col">Действия</th>
            </tr>
          </thead>
          <tbody>
            {clients.map((client) => {
              const phones = splitContactValues(client.phone);
              return (
                <tr key={client.id}>
                  <td className="fw-semibold">#{client.id}</td>
                  <td>
                    <div className="fw-semibold">
                      {client.first_name} {client.middle_name ?? ""} {client.last_name}
                    </div>
                    <div className="text-muted small">{client.email ?? phones[0] ?? "Контакт не указан"}</div>
                  </td>
                  <td>
                    <div className="fw-semibold">{client.company_name ?? "—"}</div>
                    <div className="text-muted small">
                      {client.official_company_name ?? "Официальное название пока не заполнено"}
                    </div>
                    {client.position ? <div className="text-muted small">{client.position}</div> : null}
                  </td>
                  <td className="small">
                    <div>
                      <b>ИНН:</b> {client.inn ?? "—"}
                    </div>
                    <div>
                      <EnrichmentBadge status={client.enrichment_status} />
                    </div>
                    {client.okved_code || client.okved_name ? (
                      <div className="mt-1">
                        <b>ОКВЭД:</b> {client.okved_code ?? ""} {client.okved_name ?? ""}
                      </div>
                    ) : null}
                    {client.company_status ? <div className="text-muted">Статус компании: {client.company_status}</div> : null}
                    {client.ceo_name ? <div className="text-muted">Руководитель: {client.ceo_name}</div> : null}
                    {client.company_address ? <div className="text-muted">Адрес: {client.company_address}</div> : null}
                    {client.enrichment_error ? <div className="text-danger mt-1">{client.enrichment_error}</div> : null}
                  </td>
                  <td className="small">
                    <span className="badge text-bg-light">{professionLabels[client.profession ?? ""] ?? "не задан"}</span>
                  </td>
                  <td>
                    <span className={`badge ${client.is_demo ? "text-bg-warning" : "text-bg-success"}`}>
                      {client.is_demo ? "демо" : "реальный"}
                    </span>
                  </td>
                  <td className="small">
                    {client.email ? <div className="fw-semibold text-break">{client.email}</div> : null}
                    {phones.length ? (
                      <div className="d-flex flex-column gap-1 mt-1">
                        {phones.slice(0, 2).map((phone) => (
                          <span className="badge rounded-pill text-bg-light contact-pill" key={phone}>
                            {phone}
                          </span>
                        ))}
                        {phones.length > 2 ? <div className="text-muted mt-1">ещё {phones.length - 2} номер(а)</div> : null}
                      </div>
                    ) : client.email ? null : (
                      "—"
                    )}
                  </td>
                  <td className="small">{formatDate(client.birth_date)}</td>
                  <td className="actions-col">
                    {client.enrichment_status === "enriched" && provider === "demo" ? (
                      <span className="badge text-bg-success">Готово</span>
                    ) : (
                      <button
                        className="btn btn-sm btn-outline-success action-btn"
                        disabled={busy === `client-${client.id}`}
                        onClick={() => onEnrich(client.id)}
                      >
                        {client.enrichment_status === "enriched" ? "Актуализировать" : "Обогатить"}
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
            {clients.length === 0 ? (
              <EmptyRow colSpan={9}>Клиентов пока нет. Используйте кнопку `Загрузить данные` или добавьте запись вручную.</EmptyRow>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function EnrichmentBadge({ status }: { status: string }) {
  if (status === "enriched") return <span className="badge text-bg-success">обогащено</span>;
  if (status === "pending") return <span className="badge text-bg-warning">в процессе</span>;
  if (status === "error") return <span className="badge text-bg-danger">ошибка</span>;
  return <span className="badge text-bg-secondary">{status}</span>;
}

function EventsPage({
  refreshKey,
  onChanged,
  setFlash
}: {
  refreshKey: number;
  onChanged: () => void;
  setFlash: (flash: Flash) => void;
}) {
  const state = usePageData<EventsData>(`events:${refreshKey}`, () =>
    api<EventsData>("/api/ui/events")
  );
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    try {
      await postJson<EventItem>("/api/events/manual", {
        client_id: Number(data.get("client_id")),
        title: String(data.get("title") ?? "").trim(),
        event_date: String(data.get("event_date") ?? "").trim(),
        metadata: { source: "react-manual" }
      });
      form.reset();
      setFlash({ type: "success", text: "Ручное событие создано" });
      onChanged();
    } catch (error) {
      setFlash({ type: "danger", text: error instanceof Error ? error.message : String(error) });
    } finally {
      setBusy(false);
    }
  }

  if (state.loading) return <LoadingState />;
  if (state.error) return <ErrorState error={state.error} />;
  if (!state.data) return <ErrorState error="Данные событий не получены." />;

  const data = state.data;
  const events = data.events;
  const birthdayCount = events.filter((item) => item.event_type === "birthday").length;
  const holidayCount = events.filter((item) => item.event_type === "holiday").length;
  const manualCount = events.filter((item) => item.event_type === "manual").length;
  const total = events.length;

  return (
    <>
      <div className="d-flex align-items-center justify-content-between mb-3">
        <div className="page-intro">
          <h2 className="mb-1">События</h2>
          <div className="text-muted">
            Поводы для поздравлений: дни рождения, праздники и ручные сценарии для импортированной клиентской базы.
          </div>
        </div>
      </div>

      <div className="row g-4 mb-4">
        <div className="col-12 col-md-3">
          <MetricCard label="Всего событий" value={total} hint="Все события, находящиеся в рабочем окне." />
        </div>
        <div className="col-12 col-md-3">
          <MetricCard label="Дни рождения" value={birthdayCount} hint="Персональные поводы на базе CRM-профилей." />
        </div>
        <div className="col-12 col-md-3">
          <MetricCard label="Праздники" value={holidayCount} hint="Календарные и профессиональные праздники." />
        </div>
        <div className="col-12 col-md-3">
          <MetricCard label="Ручные события" value={manualCount} hint="Управляемые поводы для реальной клиентской базы." />
        </div>
      </div>

      <div className="row g-4 mb-4">
        <div className="col-12 col-xl-6">
          <div className="surface-card">
            <div className="card-header">Создать ручное событие</div>
            <div className="card-body">
              <form className="row g-2" onSubmit={submit}>
                <div className="col-12">
                  <select className="form-select" name="client_id" required>
                    <option value="">Выберите реального клиента</option>
                    {data.clients.map((client) => (
                      <option key={client.id} value={client.id}>
                        {client.company_name ?? client.official_company_name ?? `Клиент #${client.id}`} — {client.first_name}{" "}
                        {client.last_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="col-12 col-md-8">
                  <input className="form-control" name="title" placeholder="Например: Спасибо за партнёрство" required />
                </div>
                <div className="col-12 col-md-4">
                  <input className="form-control" type="date" name="event_date" required />
                </div>
                <div className="col-12">
                  <button className="btn btn-success quick-action" disabled={busy}>
                    {busy ? "Создаю..." : "Создать событие"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>

        <div className="col-12 col-xl-6">
          <div className="surface-panel metric-card">
            <div className="metric-label mb-3">Распределение событий</div>
            <div className="events-pie-wrapper">
              <div
                className="events-pie"
                style={
                  {
                    "--val-bd": birthdayCount,
                    "--val-hol": holidayCount,
                    "--val-man": manualCount,
                    "--total": total || 1
                } as CSSProperties
                }
                data-empty={total === 0 ? "true" : undefined}
              >
                <div className="events-pie-center">
                  <span className="events-pie-total">{total}</span>
                  <span className="events-pie-label">всего</span>
                </div>
              </div>
              <div className="events-legend">
                <LegendItem label="ДР" value={birthdayCount} color="var(--primary)" />
                <LegendItem label="Праздники" value={holidayCount} color="var(--primary-dark)" />
                <LegendItem label="Ручные" value={manualCount} color="#41c77b" />
              </div>
            </div>
            <div className="events-hint text-center mt-2">
              {total > 0
                ? `ДР: ${percent(birthdayCount, total)}% | Праздники: ${percent(holidayCount, total)}% | Ручные: ${percent(
                    manualCount,
                    total
                  )}%`
                : "Нет данных для визуализации"}
            </div>
          </div>
        </div>
      </div>

      <EventsTable events={events} />
    </>
  );
}

function LegendItem({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="events-legend-item">
      <span className="events-legend-dot" style={{ background: color }} />
      <span className="events-legend-text">
        {label}: <strong>{value}</strong>
      </span>
    </div>
  );
}

function EventsTable({ events }: { events: EventItem[] }) {
  return (
    <div className="surface-card">
      <div className="card-header">Список событий</div>
      <div className="card-body table-responsive">
        <table className="table table-sm align-middle table-clean">
          <thead>
            <tr>
              <th>ID</th>
              <th>Клиент</th>
              <th>Тип</th>
              <th>Дата</th>
              <th>Повод</th>
            </tr>
          </thead>
          <tbody>
            {events.map((event) => (
              <tr key={event.id}>
                <td className="fw-semibold">#{event.id}</td>
                <td>
                  {event.client ? (
                    <>
                      <div className="fw-semibold">
                        {event.client.company_name ?? event.client.official_company_name ?? `Клиент #${event.client.id}`}
                      </div>
                      <div className="text-muted small">
                        {event.client.first_name} {event.client.last_name}
                      </div>
                    </>
                  ) : (
                    "—"
                  )}
                </td>
                <td>
                  <span className="badge text-bg-light">{eventTypeLabel(event.event_type)}</span>
                </td>
                <td>{formatDate(event.event_date)}</td>
                <td className="fw-semibold">{event.title}</td>
              </tr>
            ))}
            {events.length === 0 ? (
              <EmptyRow colSpan={5}>Событий пока нет. После seed и запуска агента окно событий заполнится автоматически.</EmptyRow>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function eventTypeLabel(type: string): string {
  if (type === "birthday") return "день рождения";
  if (type === "holiday") return "праздник";
  if (type === "manual") return "ручной повод";
  return type;
}

function GreetingsPage({
  refreshKey,
  onChanged,
  setFlash
}: {
  refreshKey: number;
  onChanged: () => void;
  setFlash: (flash: Flash) => void;
}) {
  const state = usePageData<GreetingsData>(`greetings:${refreshKey}`, () =>
    api<GreetingsData>("/api/ui/greetings")
  );

  if (state.loading) return <LoadingState />;
  if (state.error) return <ErrorState error={state.error} />;
  if (!state.data) return <ErrorState error="Данные поздравлений не получены." />;

  const greetings = state.data.greetings;
  const total = greetings.length;
  const metricSent = greetings.filter((item) => item.status === "sent").length;
  const metricReady = greetings.filter((item) => item.status === "generated" || item.status === "approved").length;
  const metricRest = Math.max(0, total - metricSent - metricReady);
  const metricWithFeedback = greetings.filter((item) => item.feedback_entries?.length).length;
  const metricWithVerdict = greetings.filter((item) =>
    item.feedback_entries?.some((feedback) => feedback.training_verdict)
  ).length;

  return (
    <>
      <div className="d-flex align-items-center justify-content-between mb-3">
        <div className="page-intro">
          <h2 className="mb-1">Поздравления</h2>
          <div className="text-muted">
            Сгенерированные поздравления, отправка по расписанию в день события и сбор отзывов с вердиктом для дообучения.
          </div>
        </div>
      </div>

      <div className="row g-4 mb-4">
        <div className="col-12 col-xl-6">
          <div className="row g-4 mb-4">
            <div className="col-12">
              <MetricCard label="Сгенерировано" value={total} hint="Всего поздравлений в системе." />
            </div>
          </div>
          <div className="row g-4">
            <div className="col-12 col-md-6">
              <MetricCard label="Отправлено" value={metricSent} hint="Статус Отправлено (хотя бы одна доставка)." />
            </div>
            <div className="col-12 col-md-6">
              <MetricCard
                label="С отзывом / вердиктом"
                value={`${metricWithFeedback} / ${metricWithVerdict}`}
                hint="Отзыв оператора и записи с вердиктом для дообучения."
              />
            </div>
          </div>
        </div>

        <div className="col-12 col-xl-6">
          <div className="surface-panel metric-card h-100">
            <div className="metric-label mb-3">Распределение по статусам отправки</div>
            <div className="approval-pie-wrapper">
              <div
                className="approval-pie"
                style={
                  {
                    "--val-new": metricReady,
                    "--val-sent": metricSent,
                    "--val-other": metricRest,
                    "--total": total || 1
                  } as CSSProperties
                }
                data-empty={total === 0 ? "true" : undefined}
              >
                <div className="approval-pie-center">
                  <span className="approval-pie-total">{total}</span>
                  <span className="approval-pie-label">всего</span>
                </div>
              </div>
              <div className="approval-legend">
                <ApprovalLegend label="В очереди на отправку" value={metricReady} color="var(--primary)" />
                <ApprovalLegend label="Отправлено" value={metricSent} color="var(--primary-dark)" />
                <ApprovalLegend label="Прочие статусы" value={metricRest} color="#9aa99e" />
              </div>
            </div>
            <div className="approval-hint text-center mt-2">
              {total > 0
                ? `Вердикт для дообучения: ${metricWithVerdict} из ${total} (${percent(metricWithVerdict, total)}%)`
                : "Нет данных для визуализации"}
            </div>
          </div>
        </div>
      </div>

      <GreetingsTable
        greetings={greetings}
        onChanged={onChanged}
        setFlash={setFlash}
      />
    </>
  );
}

function ApprovalLegend({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="approval-legend-item">
      <span className="approval-legend-dot" style={{ background: color }} />
      <span className="approval-legend-text">
        {label}: <strong>{value}</strong>
      </span>
    </div>
  );
}

function GreetingsTable({
  greetings,
  onChanged,
  setFlash
}: {
  greetings: Greeting[];
  onChanged: () => void;
  setFlash: (flash: Flash) => void;
}) {
  return (
    <div className="surface-card">
      <div className="card-header">Список поздравлений</div>
      <div className="card-body table-responsive">
        <table className="table table-sm align-middle table-clean">
          <thead>
            <tr>
              <th>ID</th>
              <th>Событие</th>
              <th>Клиент</th>
              <th>Статус</th>
              <th>Источник</th>
              <th>Обратная связь</th>
              <th>Тема</th>
              <th>Открытка</th>
            </tr>
          </thead>
          <tbody>
            {greetings.map((greeting) => (
              <GreetingRow
                key={greeting.id}
                greeting={greeting}
                onChanged={onChanged}
                setFlash={setFlash}
              />
            ))}
            {greetings.length === 0 ? (
              <EmptyRow colSpan={8}>Поздравлений пока нет. Запустите агента, чтобы заполнить эту страницу.</EmptyRow>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function GreetingRow({
  greeting,
  onChanged,
  setFlash
}: {
  greeting: Greeting;
  onChanged: () => void;
  setFlash: (flash: Flash) => void;
}) {
  const latestFeedback = greeting.feedback_entries?.[greeting.feedback_entries.length - 1];

  return (
    <tr>
      <td className="fw-semibold">#{greeting.id}</td>
      <td className="small">
        <div className="fw-semibold">{greeting.event?.title ?? greeting.event_id}</div>
        <div className="text-muted">{formatDate(greeting.event?.event_date)}</div>
      </td>
      <td className="small">
        {greeting.client ? (
          <>
            <div className="fw-semibold">
              {greeting.client.first_name} {greeting.client.middle_name ?? ""} {greeting.client.last_name}
            </div>
            {greeting.client.official_company_name || greeting.client.company_name ? (
              <div className="text-muted">{greeting.client.official_company_name ?? greeting.client.company_name}</div>
            ) : null}
            {greeting.client.okved_name ? <div className="text-muted small">ОКВЭД: {greeting.client.okved_name}</div> : null}
          </>
        ) : (
          greeting.client_id
        )}
      </td>
      <td>
        <StatusBadge status={greeting.status} />
      </td>
      <td className="small">
        <SourceBadge source={greeting.generation_source} />
      </td>
      <td className="small">
        {latestFeedback ? (
          <div className="mb-2">
            <span className="badge text-bg-success">оценка: {latestFeedback.score ?? "—"}</span>{" "}
            {latestFeedback.training_verdict === "accepted" ? <span className="badge text-bg-primary">принято</span> : null}
            {latestFeedback.training_verdict === "rejected" ? (
              <span className="badge text-bg-warning text-dark">отклонено</span>
            ) : null}
            {latestFeedback.notes ? <div className="text-muted mb-2">{latestFeedback.notes}</div> : null}
          </div>
        ) : null}
        <FeedbackForm
          greetingId={greeting.id}
          onSaved={() => {
            setFlash({ type: "success", text: "Отзыв сохранён" });
            onChanged();
          }}
          onError={(message) => setFlash({ type: "danger", text: message })}
        />
      </td>
      <td className="small">
        <div className="fw-semibold">{greeting.subject}</div>
        <GreetingText greeting={greeting} />
      </td>
      <td className="small">
        {greeting.image_url ? (
          <img src={greeting.image_url} alt="card" className="card-preview" />
        ) : (
          <div className="soft-note">Открытка появится после генерации.</div>
        )}
      </td>
    </tr>
  );
}

function SourceBadge({ source }: { source: string | null }) {
  if (!source) return <span className="text-muted">—</span>;
  if (source.includes("fewshot")) return <span className="badge text-bg-info">few-shot</span>;
  if (source === "template") return <span className="badge text-bg-secondary">template</span>;
  if (source === "llm_no_examples") return <span className="badge text-bg-light">llm</span>;
  return <span className="badge text-bg-light">{source}</span>;
}

function FeedbackForm({
  greetingId,
  onSaved,
  onError
}: {
  greetingId: number;
  onSaved: () => void;
  onError: (message: string) => void;
}) {
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    try {
      await postJson("/api/feedback", {
        greeting_id: greetingId,
        score: Number(data.get("score")),
        outcome: "unknown",
        notes: String(data.get("notes") ?? "").trim() || null
      });
      form.reset();
      onSaved();
    } catch (error) {
      onError(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="row g-1" onSubmit={submit}>
      <div className="col-12">
        <select className="form-select form-select-sm" name="score" required>
          <option value="">Оценка</option>
          <option value="1">1 — Ужасно</option>
          <option value="2">2 — Плохо</option>
          <option value="3">3 — Удовлетворительно</option>
          <option value="4">4 — Хорошо</option>
          <option value="5">5 — Отлично</option>
        </select>
      </div>
      <div className="col-12">
        <input className="form-control form-control-sm" name="notes" placeholder="Комментарий к оценке" />
      </div>
      <div className="col-12">
        <button type="submit" className="btn btn-sm btn-primary" disabled={busy}>
          {busy ? "Сохраняю..." : "Сохранить отзыв"}
        </button>
      </div>
    </form>
  );
}

function GreetingText({ greeting }: { greeting: Greeting }) {
  const [copied, setCopied] = useState("");
  const targetId = `gtext-full-${greeting.id}`;

  async function copyText() {
    try {
      await navigator.clipboard.writeText(greeting.body);
      setCopied("Скопировано");
      window.setTimeout(() => setCopied(""), 1800);
    } catch {
      setCopied("Не удалось скопировать");
    }
  }

  return (
    <div className="gtext mt-2" data-greeting-id={greeting.id}>
      <div className="gtext-preview" data-testid="greeting-text-preview">
        {greeting.body}
      </div>
      <details className="gtext-details">
        <summary className="gtext-toggle text-muted" data-testid="greeting-text-toggle">
          <span className="gtext-toggle__label-closed">Показать текст</span>
          <span className="gtext-toggle__label-open">Скрыть текст</span>
        </summary>
        <div className="gtext-actions">
          <button className="btn btn-sm btn-outline-secondary gtext-copy" type="button" onClick={copyText}>
            Скопировать
          </button>
          <span className="gtext-copy-status" aria-live="polite">
            {copied}
          </span>
        </div>
        <div className="gtext-viewer" id={targetId} data-testid="greeting-text-full">
          {greeting.body}
        </div>
      </details>
    </div>
  );
}

function DeliveriesPage({ refreshKey }: { refreshKey: number }) {
  const state = usePageData<DeliveriesData>(`deliveries:${refreshKey}`, () =>
    api<DeliveriesData>("/api/ui/deliveries")
  );
  if (state.loading) return <LoadingState />;
  if (state.error) return <ErrorState error={state.error} />;
  if (!state.data) return <ErrorState error="Данные доставок не получены." />;

  const deliveries = state.data.deliveries;
  const sentCount = deliveries.filter((item) => item.status === "sent").length;
  const errorCount = deliveries.filter((item) => item.status === "error").length;

  return (
    <>
      <div className="d-flex align-items-center justify-content-between mb-3">
        <div className="page-intro">
          <h2 className="mb-1">Доставки</h2>
          <div className="text-muted">Лог отправок и безопасных блокировок.</div>
        </div>
      </div>
      <div className="row g-4 mb-4">
        <div className="col-12 col-md-4">
          <MetricCard label="Всего доставок" value={deliveries.length} hint="Все записи доставки и логирования." />
        </div>
        <div className="col-12 col-md-4">
          <MetricCard label="Отправлено" value={sentCount} hint="Успешно записанные или отправленные сообщения." />
        </div>
        <div className="col-12 col-md-4">
          <MetricCard label="Ошибки" value={errorCount} hint="Ошибки доставки или блокировки безопасности." />
        </div>
      </div>
      <DeliveriesTable deliveries={deliveries} />
    </>
  );
}

function DeliveriesTable({ deliveries }: { deliveries: Delivery[] }) {
  return (
    <div className="surface-card">
      <div className="card-header">Список доставок</div>
      <div className="card-body table-responsive">
        <table className="table table-sm align-middle table-clean">
          <thead>
            <tr>
              <th>ID</th>
              <th>Поздравление</th>
              <th>Статус поздравления</th>
              <th>Компания</th>
              <th>Канал</th>
              <th>Получатель</th>
              <th>Статус</th>
              <th>Время отправки (МСК)</th>
              <th>Сообщение провайдера</th>
              <th>Идемпотентность</th>
            </tr>
          </thead>
          <tbody>
            {deliveries.map((delivery) => (
              <tr key={delivery.id}>
                <td className="fw-semibold">#{delivery.id}</td>
                <td>#{delivery.greeting_id}</td>
                <td className="small">{delivery.greeting?.status ?? ""}</td>
                <td className="small">{delivery.greeting?.client?.company_name ?? "—"}</td>
                <td>
                  <span className="badge text-bg-light">{delivery.channel}</span>
                </td>
                <td className="small">{delivery.recipient}</td>
                <td>
                  <StatusBadge status={delivery.status} />
                </td>
                <td className="small">{formatMskTime(delivery.sent_at)}</td>
                <td className="small">{delivery.provider_message ?? ""}</td>
                <td className="small">
                  <code className="small">{delivery.idempotency_key}</code>
                </td>
              </tr>
            ))}
            {deliveries.length === 0 ? (
              <EmptyRow colSpan={10}>Доставок пока нет. После запуска агента здесь появится outbox-журнал.</EmptyRow>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RunsPage({
  refreshKey,
  onChanged,
  setFlash
}: {
  refreshKey: number;
  onChanged: () => void;
  setFlash: (flash: Flash) => void;
}) {
  const state = usePageData<RunsData>(`runs:${refreshKey}`, () => api<RunsData>("/api/ui/runs"));
  const [busy, setBusy] = useState(false);
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  async function toggleAutonomy(enabled: boolean) {
    setBusy(true);
    try {
      await postJson(enabled ? "/api/autonomy/disable" : "/api/autonomy/enable");
      setFlash({
        type: "success",
        text: enabled ? "Автономный режим выключен." : "Автономный режим включён."
      });
      onChanged();
    } catch (error) {
      setFlash({ type: "danger", text: error instanceof Error ? error.message : String(error) });
    } finally {
      setBusy(false);
    }
  }

  if (state.loading) return <LoadingState />;
  if (state.error) return <ErrorState error={state.error} />;
  if (!state.data) return <ErrorState error="Данные запусков не получены." />;

  const data = state.data;
  const nextRunMs = data.autonomy.next_run_at ? Date.parse(data.autonomy.next_run_at) : null;
  const countdown = data.autonomy.enabled && nextRunMs ? formatCountdown(Math.max(0, nextRunMs - now)) : "--:--:--";

  return (
    <>
      <div className="d-flex align-items-center justify-content-between mb-3">
        <div className="page-intro">
          <h2 className="mb-1">Запуски агента</h2>
          <div className="text-muted">Аудит запусков, наблюдаемость конвейера и источник данных для презентации результатов.</div>
        </div>
      </div>

      <div className="row g-1 mb-4">
        <div className="col-12 col-md-3">
          <div className="surface-panel metric-card metric-card--action" style={{ paddingTop: ".7rem" }}>
            <div className="agent-control-widget" style={{ marginTop: 0 }}>
              <div className="countdown-wrapper">
                <div className="countdown-display">{countdown}</div>
                <div className="countdown-label">До следующего автозапуска (09:00)</div>
              </div>
              <div className="divider" />
              <div className="autonomy-status">
                <span className={`autonomy-pill ${data.autonomy.enabled ? "autonomy-pill--on" : "autonomy-pill--off"}`}>
                  <span className="dot" />
                  Автономный режим: {data.autonomy.enabled ? "включён" : "выключен"}
                </span>
              </div>
              <div className="actions-wrapper">
                <button
                  className="btn-control btn-manual btn-autonomy-toggle"
                  type="button"
                  disabled={busy}
                  onClick={() => toggleAutonomy(data.autonomy.enabled)}
                >
                  <span className="text">
                    {data.autonomy.enabled ? "Остановить автономный режим" : "Запустить автономный режим"}
                  </span>
                </button>
              </div>
            </div>
          </div>
        </div>
        <div className="col-12 col-md-3">
          <MetricCard label="Всего запусков" value={data.total_runs} hint="Запуски, записанные в AgentRun." className="metric-card--info" />
        </div>
        <div className="col-12 col-md-3">
          <MetricCard label="Успешно" value={data.status_totals.success} hint="Полностью успешные запуски без ошибок." className="metric-card--success" />
        </div>
        <div className="col-12 col-md-3">
          <MetricCard label="Частично" value={data.status_totals.partial} hint="Запуски с частичными ошибками." className="metric-card--warning" />
        </div>
        <div className="col-12 col-md-3">
          <MetricCard label="Ошибки" value={data.status_totals.error} hint="Фатальные ошибки, требующие внимания." className="metric-card--error" />
        </div>
      </div>

      <RunsTable runs={data.runs} />
    </>
  );
}

function formatCountdown(ms: number): string {
  const totalSec = Math.floor(ms / 1000);
  const hours = Math.floor(totalSec / 3600);
  const minutes = Math.floor((totalSec % 3600) / 60);
  const seconds = totalSec % 60;
  return [hours, minutes, seconds].map((item) => String(item).padStart(2, "0")).join(":");
}

function RunsTable({ runs, compact = false }: { runs: AgentRun[]; compact?: boolean }) {
  return (
    <div className="surface-card">
      <div className="card-header d-flex align-items-center justify-content-between">
        <span>{compact ? "Последние запуски агента" : "Последние 100 запусков"}</span>
        {compact ? <a href="/runs" className="small">Все запуски</a> : null}
      </div>
      <div className="card-body table-responsive">
        {!compact ? (
          <div className="soft-note small text-muted mb-3">
            <b>Авто-отправки</b> — отправки, которые успели выполниться в конце этого же запуска агента.
          </div>
        ) : null}
        <table className="table table-sm align-middle mb-0 table-clean">
          <thead>
            <tr>
              <th>ID</th>
              <th>Статус</th>
              <th>Источник</th>
              {!compact ? <th>Горизонт</th> : null}
              {!compact ? <th>LLM</th> : null}
              {!compact ? <th>Картинки</th> : null}
              <th>Старт (МСК)</th>
              <th>Финиш (МСК)</th>
              <th>События</th>
              <th>Поздравления</th>
              <th>{compact ? "Отправлено" : "Авто-отправка"}</th>
              {!compact ? <th>Пропущено</th> : null}
              <th>Ошибки</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id}>
                <td className="fw-semibold">
                  <a href={`/runs/${run.id}`}>#{run.id}</a>
                </td>
                <td>
                  <StatusBadge status={run.status} />
                </td>
                <td className="small">{run.triggered_by}</td>
                {!compact ? <td>{run.lookahead_days}</td> : null}
                {!compact ? <td className="small">{run.llm_mode}</td> : null}
                {!compact ? <td className="small">{run.image_mode}</td> : null}
                <td className="small">{formatMskTime(run.started_at)}</td>
                <td className="small">{formatMskTime(run.finished_at)}</td>
                <td>{run.scanned_events}</td>
                <td>{run.generated_greetings}</td>
                <td>{run.sent_deliveries}</td>
                {!compact ? <td>{run.skipped_existing}</td> : null}
                <td>{run.errors}</td>
              </tr>
            ))}
            {runs.length === 0 ? (
              <EmptyRow colSpan={compact ? 9 : 13}>История запусков пока пуста. Нажмите `Запустить агента`, чтобы наполнить журнал.</EmptyRow>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RunDetailPage({ runId, refreshKey }: { runId: number; refreshKey: number }) {
  const state = usePageData<RunDetailData>(`run:${runId}:${refreshKey}`, () =>
    api<RunDetailData>(`/api/ui/runs/${runId}`)
  );
  if (state.loading) return <LoadingState />;
  if (state.error) return <ErrorState error={state.error} />;
  if (!state.data) return <ErrorState error="Детали запуска не получены." />;

  const data = state.data;
  const run = data.run;

  return (
    <>
      <div className="d-flex flex-wrap align-items-center justify-content-between gap-3 mb-3">
        <div className="page-intro">
          <div className="text-muted small mb-2">
            <a href="/runs">Все запуски</a>
          </div>
          <h2 className="mb-1">Детали запуска #{run.id}</h2>
          <div className="text-muted">
            Что именно создал этот прогон агента, в каком статусе находятся поздравления и дошли ли они до доставки или обратной связи.
          </div>
        </div>
        <div className="d-flex flex-wrap gap-2">
          <StatusBadge status={run.status} />
          <span className="badge text-bg-light">Источник: {run.triggered_by}</span>
          <span className="badge text-bg-light">LLM: {run.llm_mode}</span>
          <span className="badge text-bg-light">Картинки: {run.image_mode}</span>
        </div>
      </div>

      <div className="row g-3 mb-4">
        <div className="col-12 col-md-3">
          <MetricCard label="События в прогоне" value={run.scanned_events} hint="Сколько событий агент просмотрел." />
        </div>
        <div className="col-12 col-md-3">
          <MetricCard label="Создано поздравлений" value={run.generated_greetings} hint="Записано именно этим запуском." />
        </div>
        <div className="col-12 col-md-3">
          <MetricCard label="Фактические доставки" value={data.actual_deliveries} hint="Все связанные доставки." />
        </div>
        <div className="col-12 col-md-3">
          <MetricCard label="С feedback" value={data.greetings_with_feedback} hint="Поздравления этого прогона с оценкой." />
        </div>
      </div>

      <div className="row g-3 mb-4">
        <div className="col-12 col-md-4">
          <MetricCard label="Авто-отправка в run" value={run.sent_deliveries} hint="Счётчик из запуска агента." />
        </div>
        <div className="col-12 col-md-4">
          <MetricCard label="Уже отправлено" value={data.actual_sent} hint="Реально отправленные доставки." />
        </div>
        <div className="col-12 col-md-4">
          <MetricCard label="Вердикт дообучения" value={data.greetings_with_training_verdict} hint="Принять/отклонить в отзыве." />
        </div>
      </div>

      <RunGreetingsTable run={run} greetings={data.greetings} />
    </>
  );
}

function RunGreetingsTable({ run, greetings }: { run: AgentRun; greetings: Greeting[] }) {
  return (
    <div className="surface-card">
      <div className="card-header d-flex align-items-center justify-content-between">
        <span>Поздравления, созданные этим запуском</span>
        <span className="small text-muted">
          Старт (МСК): {formatMskTime(run.started_at)}
          {run.finished_at ? ` | Финиш (МСК): ${formatMskTime(run.finished_at)}` : ""}
        </span>
      </div>
      <div className="card-body table-responsive">
        <table className="table table-sm align-middle table-clean">
          <thead>
            <tr>
              <th>ID</th>
              <th>Клиент</th>
              <th>Повод</th>
              <th>Статус</th>
              <th>Доставки</th>
              <th>Feedback</th>
              <th>Создано</th>
            </tr>
          </thead>
          <tbody>
            {greetings.map((greeting) => {
              const latestFeedback = greeting.feedback_entries?.[greeting.feedback_entries.length - 1];
              const sentDeliveries = greeting.deliveries?.filter((delivery) => delivery.status === "sent").length ?? 0;
              return (
                <tr key={greeting.id}>
                  <td className="fw-semibold">#{greeting.id}</td>
                  <td>
                    {greeting.client ? (
                      <>
                        <div className="fw-semibold">
                          {greeting.client.last_name} {greeting.client.first_name}
                        </div>
                        <div className="small text-muted">{greeting.client.company_name ?? "Без компании"}</div>
                      </>
                    ) : (
                      <span className="text-muted">Клиент не найден</span>
                    )}
                  </td>
                  <td>
                    {greeting.event ? (
                      <>
                        <div className="fw-semibold">{greeting.event.title}</div>
                        <div className="small text-muted">
                          {greeting.event.event_type} | {formatDate(greeting.event.event_date)}
                        </div>
                      </>
                    ) : (
                      <span className="text-muted">Событие удалено</span>
                    )}
                  </td>
                  <td>
                    <StatusBadge status={greeting.status} />
                  </td>
                  <td>
                    {greeting.deliveries?.length ? (
                      <>
                        <div className="fw-semibold">{greeting.deliveries.length}</div>
                        <div className="small text-muted">sent={sentDeliveries}</div>
                      </>
                    ) : (
                      <span className="text-muted">нет</span>
                    )}
                  </td>
                  <td>
                    {latestFeedback ? (
                      <>
                        <div className="fw-semibold">{latestFeedback.outcome}</div>
                        <div className="small text-muted">score={latestFeedback.score ?? "n/a"}</div>
                      </>
                    ) : (
                      <span className="text-muted">нет</span>
                    )}
                  </td>
                  <td className="small">{formatDateTime(greeting.created_at)}</td>
                </tr>
              );
            })}
            {greetings.length === 0 ? (
              <EmptyRow colSpan={7}>Этот запуск не создал новых поздравлений. Возможно, все события уже были обработаны ранее.</EmptyRow>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function NotFoundPage() {
  return (
    <div className="surface-panel empty-state">
      Страница не найдена. Можно вернуться на <a href="/">дашборд</a>.
    </div>
  );
}

export default function App() {
  const [path, setPath] = useState(window.location.pathname);
  const [flash, setFlash] = useState<Flash>(null);
  const [actionBusy, setActionBusy] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const listener = () => setPath(window.location.pathname);
    window.addEventListener("popstate", listener);
    return () => window.removeEventListener("popstate", listener);
  }, []);

  function navigate(nextPath: string) {
    window.history.pushState({}, "", nextPath);
    setPath(window.location.pathname);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function refresh() {
    setRefreshKey((value) => value + 1);
  }

  async function runGlobalAction(name: string, pathToPost: string, nextPath: string, successText: string) {
    setActionBusy(name);
    try {
      const result = await postJson<{ message?: string }>(pathToPost);
      setFlash({ type: "success", text: result.message ?? successText });
      refresh();
      navigate(nextPath);
    } catch (error) {
      setFlash({ type: "danger", text: error instanceof Error ? error.message : String(error) });
    } finally {
      setActionBusy(null);
    }
  }

  const runIdMatch = path.match(/^\/runs\/(\d+)$/);
  const page = runIdMatch ? (
    <RunDetailPage runId={Number(runIdMatch[1])} refreshKey={refreshKey} />
  ) : path === "/" ? (
    <DashboardPage refreshKey={refreshKey} />
  ) : path === "/clients" ? (
    <ClientsPage refreshKey={refreshKey} onChanged={refresh} setFlash={setFlash} />
  ) : path === "/events" ? (
    <EventsPage refreshKey={refreshKey} onChanged={refresh} setFlash={setFlash} />
  ) : path === "/greetings" ? (
    <GreetingsPage refreshKey={refreshKey} onChanged={refresh} setFlash={setFlash} />
  ) : path === "/deliveries" ? (
    <DeliveriesPage refreshKey={refreshKey} />
  ) : path === "/project-planner" ? (
    <ProjectPlannerPage />
  ) : path === "/runs" ? (
    <RunsPage refreshKey={refreshKey} onChanged={refresh} setFlash={setFlash} />
  ) : (
    <NotFoundPage />
  );

  return (
    <Layout
      path={path}
      flash={flash}
      actionBusy={actionBusy}
      onNavigate={navigate}
      onRunAgent={() => runGlobalAction("run", "/api/ui/agent/run-once", "/greetings", "Агент запущен.")}
      onSeedDemo={() => runGlobalAction("seed", "/api/ui/seed-demo", "/clients", "Демо-данные загружены.")}
      onResetRuntime={() => runGlobalAction("reset", "/api/ui/reset-runtime", "/", "Среда очищена.")}
    >
      {page}
    </Layout>
  );
}
