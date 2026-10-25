export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

type QueryValue = string | number | boolean | undefined | null;

export interface RequestOptions {
  /** false nas chamadas que ainda nao tem token (login) */
  auth?: boolean;
  query?: Record<string, QueryValue>;
}

export interface ClientConfig {
  getToken: () => string | null;
  onUnauthorized: () => void;
  fetchImpl?: typeof fetch;
}

const NETWORK_DETAIL = "Sem conexão com o servidor.";
const INVALID_DETAIL = "Dados inválidos.";

function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  if (!query) return path;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    params.set(key, String(value));
  }
  const text = params.toString();
  return text ? `${path}?${text}` : path;
}

function detailOf(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return INVALID_DETAIL;
  }
  return `Erro ${status}.`;
}

export function createClient(config: ClientConfig) {
  const doFetch = config.fetchImpl ?? ((...args: Parameters<typeof fetch>) => fetch(...args));

  async function request<T>(
    method: string,
    path: string,
    body?: unknown,
    options: RequestOptions = {},
  ): Promise<T> {
    const headers: Record<string, string> = { Accept: "application/json" };
    const token = options.auth === false ? null : config.getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    const init: RequestInit = { method, headers };
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(body);
    }

    let response: Response;
    try {
      response = await doFetch(buildUrl(path, options.query), init);
    } catch {
      throw new ApiError(0, NETWORK_DETAIL);
    }

    if (response.status === 204) return undefined as T;
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    if (!response.ok) {
      if (response.status === 401 && token) config.onUnauthorized();
      throw new ApiError(response.status, detailOf(payload, response.status));
    }
    return payload as T;
  }

  return { request };
}

export type Client = ReturnType<typeof createClient>;
