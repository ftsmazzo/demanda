import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AppRoutes } from "../App";
import type { Me } from "../api/types";
import { COLABORADOR, SOCIO, makeBoard } from "../test/fixtures";
import { renderApp, type Handlers } from "../test/utils";

const hoursAgo = (hours: number) => new Date(Date.now() - hours * 3_600_000).toISOString();

function open(health: unknown, me: Me = SOCIO) {
  const handlers: Handlers = {
    "GET /api/v1/me": () => [200, me],
    "GET /api/v1/board": () => [200, makeBoard([])],
    "GET /api/v1/users": () => [200, []],
    "GET /api/v1/channels/health": () => [200, health],
  };
  return renderApp(<AppRoutes />, { signedIn: true, handlers });
}

describe("channel alert", () => {
  it("warns when the WhatsApp listener is disconnected and says since when", async () => {
    open([{ id: "c1", name: "Principal", state: "close", healthy: false, changed_at: hoursAgo(3), checked_at: hoursAgo(0) }]);

    const alert = await screen.findByRole("alert");

    expect(alert).toHaveTextContent("O WhatsApp “Principal” está desconectado há 3 h.");
    expect(alert).toHaveTextContent("podem não aparecer");
  });

  it("stays quiet when every channel is healthy", async () => {
    open([{ id: "c1", name: "Principal", state: "open", healthy: true, changed_at: hoursAgo(5), checked_at: hoursAgo(0) }]);
    await screen.findByRole("heading", { name: "Novas" });

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("does not ask a collaborator, who cannot act on it", async () => {
    const { calls } = open([{ id: "c1", name: "Principal", state: "close", healthy: false, changed_at: null, checked_at: null }], COLABORADOR);
    await screen.findByRole("main");

    expect(calls.some((call) => call.key === "GET /api/v1/channels/health")).toBe(false);
  });
});
