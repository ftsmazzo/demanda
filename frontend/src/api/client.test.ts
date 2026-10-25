import { describe, expect, it, vi } from "vitest";
import { ApiError, createClient } from "./client";

function respond(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function setup(response: Response | Error, token: string | null = "tok") {
  const fetchImpl = vi.fn(async (_url: string, _init?: RequestInit) => {
    if (response instanceof Error) throw response;
    return response;
  });
  const onUnauthorized = vi.fn();
  const client = createClient({ getToken: () => token, onUnauthorized, fetchImpl: fetchImpl as unknown as typeof fetch });
  return { client, fetchImpl, onUnauthorized };
}

describe("api client", () => {
  it("sends the bearer token and parses json", async () => {
    const { client, fetchImpl } = setup(respond(200, { ok: true }));

    const data = await client.request<{ ok: boolean }>("GET", "/api/v1/me");

    expect(data).toEqual({ ok: true });
    const [url, init] = fetchImpl.mock.calls[0];
    expect(url).toBe("/api/v1/me");
    expect(((init as RequestInit).headers as Record<string, string>).Authorization).toBe("Bearer tok");
  });

  it("does not send Authorization without a token", async () => {
    const { client, fetchImpl } = setup(respond(200, {}), null);

    await client.request("GET", "/api/v1/board");

    const init = fetchImpl.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  it("sends json bodies with the right content type", async () => {
    const { client, fetchImpl } = setup(respond(200, {}));

    await client.request("PATCH", "/api/v1/demands/1", { status: "novo" });

    const init = fetchImpl.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("PATCH");
    expect(init.body).toBe(JSON.stringify({ status: "novo" }));
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });

  it("turns error responses into ApiError with the server detail", async () => {
    const { client } = setup(respond(404, { detail: "demanda nao encontrada" }));

    const failure = client.request("GET", "/api/v1/demands/x");

    await expect(failure).rejects.toMatchObject({ status: 404, detail: "demanda nao encontrada" });
    await expect(failure).rejects.toBeInstanceOf(ApiError);
  });

  it("summarizes validation errors from the server", async () => {
    const { client } = setup(respond(422, { detail: [{ loc: ["body", "title"], msg: "x" }] }));

    await expect(client.request("POST", "/api/v1/demands", {})).rejects.toMatchObject({
      status: 422,
      detail: "Dados inválidos.",
    });
  });

  it("signals an expired session on 401 when a token was sent", async () => {
    const { client, onUnauthorized } = setup(respond(401, { detail: "nao autenticado" }));

    await expect(client.request("GET", "/api/v1/me")).rejects.toMatchObject({ status: 401 });

    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it("does not treat a failed login as an expired session", async () => {
    const { client, onUnauthorized } = setup(respond(401, { detail: "credenciais invalidas" }));

    await expect(
      client.request("POST", "/api/v1/auth/login", {}, { auth: false }),
    ).rejects.toMatchObject({ status: 401 });

    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it("reports network failures as status 0", async () => {
    const { client } = setup(new TypeError("Failed to fetch"));

    await expect(client.request("GET", "/api/v1/me")).rejects.toMatchObject({
      status: 0,
      detail: "Sem conexão com o servidor.",
    });
  });

  it("returns undefined for 204 responses", async () => {
    const { client } = setup(new Response(null, { status: 204 }));

    expect(await client.request("DELETE", "/api/v1/x")).toBeUndefined();
  });

  it("builds query strings and skips empty values", async () => {
    const { client, fetchImpl } = setup(respond(200, {}));

    await client.request("GET", "/api/v1/board", undefined, {
      query: { sector: "fiscal", assignee: "", q: undefined, limit: 20 },
    });

    expect(fetchImpl.mock.calls[0][0]).toBe("/api/v1/board?sector=fiscal&limit=20");
  });
});
