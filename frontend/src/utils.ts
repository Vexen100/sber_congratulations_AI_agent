export const professionLabels: Record<string, string> = {
  management: "управление",
  finance: "финансы",
  accounting: "бухгалтерия",
  it: "IT",
  hr: "HR",
  marketing: "маркетинг",
  sales: "продажи",
  logistics: "логистика",
  construction: "строительство",
  medicine: "медицина",
  security: "безопасность"
};

export function formatDate(value: string | null | undefined): string {
  if (!value) return "";
  return value.slice(0, 10);
}

export function formatMskTime(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone: "Europe/Moscow",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("ru-RU", {
    dateStyle: "short",
    timeStyle: "medium"
  }).format(date);
}

export function percent(part: number, total: number): number {
  return total > 0 ? Math.round((part / total) * 100) : 0;
}

export function splitContactValues(value: string | null | undefined): string[] {
  return (value ?? "")
    .replace(/\r/g, "\n")
    .replace(/[;\n]/g, ",")
    .split(",")
    .map((chunk) => chunk.replace(/\s+/g, " ").trim().replace(/^,+|,+$/g, ""))
    .filter(Boolean);
}

export function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    success: "успех",
    partial: "частично",
    error: "ошибка",
    running: "в работе",
    sent: "отправлено",
    generated: "generated",
    approved: "согласовано",
    needs_approval: "очередь",
    skipped: "пропущено",
    rejected: "отклонено"
  };
  return labels[status] ?? status;
}

export function statusBadgeClass(status: string): string {
  if (status === "success" || status === "sent") return "text-bg-success";
  if (status === "partial" || status === "needs_approval") return "text-bg-warning";
  if (status === "error") return "text-bg-danger";
  if (status === "generated") return "text-bg-primary";
  if (status === "approved") return "text-bg-info";
  if (status === "rejected") return "text-bg-dark";
  return "text-bg-secondary";
}
