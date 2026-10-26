import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AppRoutes } from "../../App";
import { SOCIO, USERS, makeBoard, makeCard } from "../../test/fixtures";
import { renderApp } from "../../test/utils";

function open(cards: ReturnType<typeof makeCard>[]) {
  return renderApp(<AppRoutes />, {
    route: "/quadro",
    signedIn: true,
    handlers: {
      "GET /api/v1/me": () => [200, SOCIO],
      "GET /api/v1/board": () => [200, makeBoard(cards)],
      "GET /api/v1/users": () => [200, USERS],
    },
  });
}

describe("case card", () => {
  it("shows the AI summary under the title", async () => {
    open([makeCard({ title: "Férias de Ana", summary: "Ana pediu férias para dezembro." })]);

    const card = (await screen.findByText("Férias de Ana")).closest("button")!;

    expect(within(card).getByText("Ana pediu férias para dezembro.")).toBeInTheDocument();
  });

  it("flags a case waiting for confirmation", async () => {
    open([makeCard({ title: "Incerto", needs_review: true, review_reason: "confirmar agrupamento" })]);

    const card = (await screen.findByText("Incerto")).closest("button")!;

    expect(within(card).getByText("Confirmar")).toBeInTheDocument();
  });

  it("names the kind of a card that is not an ordinary task", async () => {
    open([makeCard({ title: "Cobrar extratos", kind: "cobranca" }), makeCard({ title: "Tarefa comum", kind: "tarefa" })]);

    const charge = (await screen.findByText("Cobrar extratos")).closest("button")!;
    const task = screen.getByText("Tarefa comum").closest("button")!;

    expect(within(charge).getByText("Cobrança")).toBeInTheDocument();
    expect(within(task).queryByText("Tarefa")).not.toBeInTheDocument();
  });

  it("stays clean for an ordinary card", async () => {
    open([makeCard({ title: "Normal" })]);

    const card = (await screen.findByText("Normal")).closest("button")!;

    expect(within(card).queryByText("Confirmar")).not.toBeInTheDocument();
  });
});
