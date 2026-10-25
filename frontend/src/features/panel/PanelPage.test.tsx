import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { AppRoutes } from "../../App";
import { SOCIO, USERS, makeBoard, makeCard, makeDetail } from "../../test/fixtures";
import { renderApp, type Handlers } from "../../test/utils";

const ana = { id: "u-1", name: "Ana Lima" };

function handlers(cards = [
  makeCard({ id: "a", title: "Certidão negativa", idle_hours: 80, assignee: ana, sector: "societario" }),
  makeCard({ id: "b", title: "Guia do DAS", idle_hours: 6, assignee: ana }),
  makeCard({ id: "c", title: "Folha de outubro", idle_hours: 30, assignee: null, sector: "dp" }),
]): Handlers {
  return {
    "GET /api/v1/me": () => [200, SOCIO],
    "GET /api/v1/board": () => [200, makeBoard(cards)],
    "GET /api/v1/users": () => [200, USERS],
    "GET /api/v1/demands/a": () => [200, makeDetail({ id: "a", title: "Certidão negativa" })],
  };
}

describe("owner panel", () => {
  it("names the most forgotten demand in the opening sentence", async () => {
    renderApp(<AppRoutes />, { route: "/painel", signedIn: true, handlers: handlers() });

    expect(await screen.findByText("A demanda mais esquecida está parada há 3 dias: Certidão negativa.")).toBeInTheDocument();
  });

  it("lists the stuck demands, oldest first, and opens one in the drawer", async () => {
    renderApp(<AppRoutes />, { route: "/painel", signedIn: true, handlers: handlers() });

    const rows = await screen.findAllByRole("button", { name: /Certidão negativa|Folha de outubro|Guia do DAS/ });
    expect(rows.map((row) => within(row).getByText(/Certidão|Folha|Guia/).textContent)).toEqual([
      "Certidão negativa",
      "Folha de outubro",
      "Guia do DAS",
    ]);

    await userEvent.click(rows[0]);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("shows the team load with the number of open demands", async () => {
    renderApp(<AppRoutes />, { route: "/painel", signedIn: true, handlers: handlers() });

    expect(await screen.findByRole("img", { name: "Ana Lima: 2 demandas abertas" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Sem responsável: 1 demanda aberta" })).toBeInTheDocument();
  });

  it("says so when nothing is open", async () => {
    renderApp(<AppRoutes />, { route: "/painel", signedIn: true, handlers: handlers([]) });

    expect(await screen.findByText("Nenhuma demanda aberta. Tudo em dia.")).toBeInTheDocument();
  });
});
