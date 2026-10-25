import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../auth/AuthContext";
import { saveSession } from "../auth/session";

type Handler = (req: { body: any; url: URL }) => [number, unknown] | Promise<[number, unknown]>;
export type Handlers = Record<string, Handler>;

export function mockFetch(handlers: Handlers) {
  const calls: { key: string; body: any; url: URL }[] = [];
  const fetchImpl = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://test.local");
    const key = `${init?.method ?? "GET"} ${url.pathname}`;
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ key, body, url });
    const handler = handlers[key];
    if (!handler) {
      return new Response(JSON.stringify({ detail: `sem rota de teste: ${key}` }), { status: 404 });
    }
    const [status, payload] = await handler({ body, url });
    return new Response(payload === undefined ? null : JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  }) as unknown as typeof fetch;
  return { fetchImpl, calls };
}

interface RenderOptions {
  route?: string;
  handlers?: Handlers;
  /** comeca com uma sessao valida salva */
  signedIn?: boolean;
}

export function renderApp(ui: ReactElement, options: RenderOptions = {}) {
  const { route = "/", handlers = {}, signedIn = false } = options;
  if (signedIn) saveSession({ token: "token-de-teste", expiresAt: Date.now() + 3_600_000 });
  const mock = mockFetch(handlers);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const result = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <AuthProvider fetchImpl={mock.fetchImpl}>{ui}</AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...result, ...mock, client };
}
