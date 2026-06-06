type RequestOptions = {
  method?: "GET" | "POST";
  body?: unknown;
};

type ApiErrorPayload = {
  detail?: unknown;
  message?: string;
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function parseError(resp: Response): Promise<string> {
  try {
    const payload = (await resp.json()) as ApiErrorPayload;
    if (typeof payload.detail === "string") return payload.detail;
    if (typeof payload.message === "string") return payload.message;
    if (payload.detail) return JSON.stringify(payload.detail);
  } catch {
    // Fall through to the HTTP status line.
  }
  return `HTTP ${resp.status}`;
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const resp = await fetch(path, {
    method: options.method ?? "GET",
    headers: {
      Accept: "application/json",
      ...(options.body === undefined ? {} : { "Content-Type": "application/json" })
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body)
  });

  if (!resp.ok) {
    throw new ApiError(await parseError(resp), resp.status);
  }

  return (await resp.json()) as T;
}

export function postJson<T>(path: string, body?: unknown): Promise<T> {
  return api<T>(path, { method: "POST", body });
}
