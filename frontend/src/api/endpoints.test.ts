import { describe, expect, it, vi } from "vitest";
import { createClient } from "./client";
import { createApi } from "./endpoints";

function setup() {
  const fetchImpl = vi.fn(async (_url: string, _init?: RequestInit) => new Response("{}", { status: 200 }));
  const client = createClient({ getToken: () => "t", onUnauthorized: vi.fn(), fetchImpl: fetchImpl as unknown as typeof fetch });
  return { api: createApi(client), fetchImpl };
}

describe("endpoints", () => {
  it("accepts ordinary ids", async () => {
    const { api, fetchImpl } = setup();

    await api.demand("3f2b8c1e-aaaa-bbbb-cccc-1234567890ab");

    expect(fetchImpl.mock.calls[0][0]).toBe("/api/v1/demands/3f2b8c1e-aaaa-bbbb-cccc-1234567890ab");
  });

  it.each(["../users", "..", "a/b", "a?x=1", "", "%2e%2e"])("refuses the id %j without calling the server", async (id) => {
    const { api, fetchImpl } = setup();

    expect(() => api.demand(id)).toThrow(/invalido/);
    expect(() => api.patchDemand(id, { title: "x" })).toThrow(/invalido/);
    expect(() => api.addSubtask(id, "x")).toThrow(/invalido/);
    expect(() => api.patchSubtask(id, { done: true })).toThrow(/invalido/);
    expect(() => api.patchContact(id, { name: "x" })).toThrow(/invalido/);
    expect(fetchImpl).not.toHaveBeenCalled();
  });
});
