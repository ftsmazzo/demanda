import { describe, expect, it, vi } from "vitest";
import { clearSession, loadSession, rememberTenant, rememberedTenant, saveSession } from "./session";

const future = () => Date.now() + 60_000;

describe("session", () => {
  it("round-trips a valid session", () => {
    saveSession({ token: "abc", expiresAt: future() });

    expect(loadSession()).toMatchObject({ token: "abc" });
  });

  it("drops expired sessions", () => {
    saveSession({ token: "abc", expiresAt: Date.now() - 1 });

    expect(loadSession()).toBeNull();
    expect(sessionStorage.length).toBe(0);
  });

  it("ignores corrupted storage", () => {
    sessionStorage.setItem("demanda.session", "{nao e json");

    expect(loadSession()).toBeNull();
  });

  it("clears the session", () => {
    saveSession({ token: "abc", expiresAt: future() });

    clearSession();

    expect(loadSession()).toBeNull();
  });

  it("survives a storage that throws", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("blocked");
    });

    expect(() => saveSession({ token: "abc", expiresAt: future() })).not.toThrow();
    expect(() => rememberTenant("x")).not.toThrow();
  });

  it("remembers the company slug between visits", () => {
    expect(rememberedTenant()).toBe("");

    rememberTenant("contabilidade-piloto");

    expect(rememberedTenant()).toBe("contabilidade-piloto");
  });
});
