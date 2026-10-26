import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { AppRoutes } from "../../App";
import type { Me } from "../../api/types";
import { COLABORADOR, GESTOR, SOCIO, USERS, makeBoard, makeCard } from "../../test/fixtures";
import { renderApp, type Handlers } from "../../test/utils";

const julia = { id: "u-9", name: "Juliana Prado" };

const cards = () => [
  makeCard({ id: "a", title: "Já pedi 3 vezes a certidão", urgency: "critica", sector: "societario", idle_hours: 26, assignee: julia, progress: { done: 0, total: 3, percent: 0 } }),
  makeCard({ id: "b", title: "Quando vence o DAS?", sector: "fiscal", idle_hours: 52, contact: { id: "c-2", name: "Oficina do Zé", phone: "5511999990103", kind: "cliente", priority: false } }),
  makeCard({ id: "c", title: "Abertura da filial", status: "em_andamento", sector: "societario", urgency: "alta", idle_hours: 20, assignee: julia, progress: { done: 2, total: 5, percent: 40 } }),
  makeCard({ id: "d", title: "Pedido de folga", sector: "rh-interno", idle_hours: 6 }),
  makeCard({ id: "e", title: "Alvará renovado", status: "concluido", closed_at: "2026-10-22T12:00:00Z", idle_hours: 0 }),
];

function handlersFor(me: Me, board = makeBoard(cards())): Handlers {
  return {
    "GET /api/v1/me": () => [200, me],
    "GET /api/v1/board": () => [200, board],
    "GET /api/v1/users": () => [200, USERS],
  };
}

async function openBoard(me: Me = SOCIO, handlers = handlersFor(me)) {
  const view = renderApp(<AppRoutes />, { route: "/quadro", signedIn: true, handlers });
  await screen.findByRole("heading", { name: "Novas" });
  return view;
}

describe("board", () => {
  it("shows the four lanes with their counts", async () => {
    await openBoard();

    for (const name of ["Novas", "Em andamento", "Aguardando", "Concluídas"]) {
      expect(screen.getByRole("heading", { name })).toBeInTheDocument();
    }
    const novas = screen.getByRole("region", { name: "Novas" });
    expect(within(novas).getByText("3")).toBeInTheDocument();
  });

  it("tells the story of the day in one sentence", async () => {
    await openBoard();

    expect(
      screen.getByText("Hoje, 1 demanda crítica pede a sua atenção e 2 estão paradas há mais de um dia."),
    ).toBeInTheDocument();
  });

  it("shows what matters on each card", async () => {
    await openBoard();

    const card = screen.getByRole("button", { name: /Já pedi 3 vezes/ });
    expect(within(card).getByText("Padaria Pão Quente")).toBeInTheDocument();
    expect(within(card).getByText("Societário")).toBeInTheDocument();
    expect(within(card).getByText("Crítica")).toBeInTheDocument();
    expect(within(card).getByText("há 1 dia")).toBeInTheDocument();
    expect(within(card).getByText("0 de 3")).toBeInTheDocument();
    expect(within(card).getByLabelText("Juliana Prado")).toHaveTextContent("JP");
  });

  it("marks cards without owner or steps plainly", async () => {
    await openBoard();

    const card = screen.getByRole("button", { name: /Quando vence o DAS/ });
    expect(within(card).getByText("Sem etapas")).toBeInTheDocument();
    expect(within(card).getByLabelText("Sem responsável")).toBeInTheDocument();
    expect(within(card).getByText("há 2 dias")).toBeInTheDocument();
  });

  it("flags restricted HR demands for people who can see them", async () => {
    await openBoard();

    const card = screen.getByRole("button", { name: /Pedido de folga/ });
    expect(within(card).getByLabelText("Acesso restrito")).toBeInTheDocument();
  });

  it("describes how long ago a demand was closed", async () => {
    await openBoard();

    const card = screen.getByRole("button", { name: /Alvará renovado/ });
    expect(within(card).getByText(/Concluída há/)).toBeInTheDocument();
  });

  it("invites action on an empty lane", async () => {
    await openBoard();

    const aguardando = screen.getByRole("region", { name: "Aguardando" });
    expect(within(aguardando).getByText(/Nada por aqui/)).toBeInTheDocument();
  });

  it("filters by sector on the server", async () => {
    const user = userEvent.setup({ delay: null });
    const { calls } = await openBoard();

    await user.selectOptions(screen.getByLabelText("Filtrar por setor"), "fiscal");

    await screen.findByRole("heading", { name: "Novas" });
    const last = calls.filter((call) => call.key === "GET /api/v1/board").at(-1)!;
    expect(last.url.searchParams.get("sector")).toBe("fiscal");
  });

  it("filters by person for managers", async () => {
    const user = userEvent.setup({ delay: null });
    const { calls } = await openBoard();

    await user.selectOptions(screen.getByLabelText("Filtrar por pessoa"), "Bruno Costa");

    await screen.findByRole("heading", { name: "Novas" });
    const last = calls.filter((call) => call.key === "GET /api/v1/board").at(-1)!;
    expect(last.url.searchParams.get("assignee")).toBe("u-3");
  });

  it("gives a colaborador a simpler toolbar", async () => {
    await openBoard(COLABORADOR);

    expect(screen.queryByLabelText("Filtrar por pessoa")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Nova demanda" })).not.toBeInTheDocument();
  });

  it("lets socios and gestores start a new demand", async () => {
    await openBoard(GESTOR);

    expect(screen.getByRole("button", { name: "Nova demanda" })).toBeInTheDocument();
  });

  it("selects a card when it is opened", async () => {
    const user = userEvent.setup({ delay: null });
    await openBoard();

    const card = screen.getByRole("button", { name: /Quando vence o DAS/ });
    await user.click(card);

    expect(card).toHaveAttribute("aria-current", "true");
  });

  it("says it is loading and can recover from a failure", async () => {
    const user = userEvent.setup({ delay: null });
    let fail = true;
    const handlers = {
      ...handlersFor(SOCIO),
      "GET /api/v1/board": () => (fail ? ([500, { detail: "x" }] as [number, unknown]) : ([200, makeBoard(cards())] as [number, unknown])),
    };
    renderApp(<AppRoutes />, { route: "/quadro", signedIn: true, handlers });

    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível carregar o quadro.");
    fail = false;
    await user.click(screen.getByRole("button", { name: "Tentar de novo" }));

    expect(await screen.findByRole("heading", { name: "Novas" })).toBeInTheDocument();
  });

  it("opens a demand with Enter from the keyboard", async () => {
    await openBoard();

    screen.getByRole("button", { name: /Quando vence o DAS/ }).focus();
    await userEvent.keyboard("{Enter}");

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });
});
