import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../../App";
import type { Appointment, Me } from "../../api/types";
import { COLABORADOR, SOCIO, makeBoard, makeDetail } from "../../test/fixtures";
import { renderApp, type Handlers } from "../../test/utils";

// segunda-feira 26/10/2026, 12:00 em Sao Paulo
beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date("2026-10-26T15:00:00Z"));
});
afterEach(() => vi.useRealTimers());

const base: Appointment = {
  id: "a1",
  title: "Reunião do projeto IE",
  starts_at: "2026-10-28T17:00:00Z", // quarta 14:00
  all_day: false,
  status: "proposed",
  demand_id: "d1",
  sector: "societario",
  contact: { id: "c1", name: "Poli", phone: "5511999990101", kind: "cliente", priority: false },
};
const allDay: Appointment = { ...base, id: "a2", title: "Visita ao cliente", all_day: true, status: "confirmed", starts_at: "2026-10-29T03:00:00Z", contact: null };

function open(list: Appointment[], me: Me = SOCIO, extra: Handlers = {}, route = "/agenda") {
  return renderApp(<AppRoutes />, {
    route,
    signedIn: true,
    handlers: {
      "GET /api/v1/me": () => [200, me],
      "GET /api/v1/board": () => [200, makeBoard([])],
      "GET /api/v1/appointments": () => [200, list],
      "GET /api/v1/demands/d1": () => [200, makeDetail({ id: "d1", title: "Reunião IE" })],
      ...extra,
    },
  });
}

const patched = (calls: { key: string; body: unknown }[], key: string) => calls.find((c) => c.key === key)?.body;

describe("agenda: week", () => {
  it("opens on the current week with each appointment on its day and time", async () => {
    open([base]);

    expect(await screen.findByText("26 de outubro a 1 de novembro de 2026")).toBeInTheDocument();
    const wednesday = screen.getByRole("group", { name: "quarta-feira, 28/10" });
    const event = within(wednesday).getByRole("button", { name: /14:00 Reunião do projeto IE/ });
    expect(event).toHaveAttribute("data-status", "proposed");
    expect(within(screen.getByRole("group", { name: "terça-feira, 27/10" })).queryByRole("button")).not.toBeInTheDocument();
  });

  it("puts all-day appointments in their own strip", async () => {
    open([allDay]);

    const thursday = await screen.findByRole("group", { name: "quinta-feira, 29/10 o dia todo" });

    expect(within(thursday).getByRole("button", { name: /Visita ao cliente/ })).toBeInTheDocument();
  });

  it("asks the server only for the visible week and moves forward and back", async () => {
    const { calls } = open([base]);
    await screen.findByText("26 de outubro a 1 de novembro de 2026");

    await userEvent.click(screen.getByRole("button", { name: "Semana seguinte" }));

    expect(await screen.findByText("2 a 8 de novembro de 2026")).toBeInTheDocument();
    const last = calls.filter((c) => c.key === "GET /api/v1/appointments").at(-1)!;
    expect(last.url.searchParams.get("since")).toContain("2026-11-02");
    await userEvent.click(screen.getByRole("button", { name: "Hoje" }));
    expect(await screen.findByText("26 de outubro a 1 de novembro de 2026")).toBeInTheDocument();
  });

  it("says when the week is empty", async () => {
    open([]);

    expect(await screen.findByText("Semana sem compromissos.")).toBeInTheDocument();
  });
});

describe("agenda: details and actions", () => {
  it("shows the selected appointment and confirms it", async () => {
    const key = "PATCH /api/v1/appointments/a1";
    const { calls } = open([base], SOCIO, { [key]: ({ body }) => [200, { ...base, ...(body as object) }] });

    await userEvent.click(await screen.findByRole("button", { name: /14:00 Reunião do projeto IE/ }));
    const panel = screen.getByRole("region", { name: "Compromisso selecionado" });
    expect(within(panel).getByText("quarta-feira, 28/10 às 14:00")).toBeInTheDocument();
    expect(within(panel).getByText("Poli")).toBeInTheDocument();
    await userEvent.click(within(panel).getByRole("button", { name: "Confirmar" }));

    await waitFor(() => expect(patched(calls, key)).toEqual({ status: "confirmed" }));
  });

  it("cancels, and a colaborador can only look", async () => {
    const key = "PATCH /api/v1/appointments/a2";
    const { calls } = open([allDay], SOCIO, { [key]: ({ body }) => [200, { ...allDay, ...(body as object) }] });
    await userEvent.click(await screen.findByRole("button", { name: /Visita ao cliente/ }));
    await userEvent.click(within(screen.getByRole("region", { name: "Compromisso selecionado" })).getByRole("button", { name: "Cancelar" }));
    await waitFor(() => expect(patched(calls, key)).toEqual({ status: "cancelled" }));
  });

  it("is read-only for a colaborador", async () => {
    open([base], COLABORADOR);

    await userEvent.click(await screen.findByRole("button", { name: /14:00 Reunião do projeto IE/ }));

    const panel = screen.getByRole("region", { name: "Compromisso selecionado" });
    expect(within(panel).queryByRole("button", { name: "Confirmar" })).not.toBeInTheDocument();
    expect(within(panel).queryByRole("button", { name: "Cancelar" })).not.toBeInTheDocument();
  });

  it("opens the case and links to the conversation", async () => {
    open([base]);
    await userEvent.click(await screen.findByRole("button", { name: /14:00 Reunião do projeto IE/ }));
    const panel = screen.getByRole("region", { name: "Compromisso selecionado" });

    expect(within(panel).getByRole("link", { name: "Ver a conversa" })).toHaveAttribute("href", "/contatos/c1/conversa");
    await userEvent.click(within(panel).getByRole("button", { name: "Abrir o caso" }));
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("explains a failed change", async () => {
    open([base], SOCIO, { "PATCH /api/v1/appointments/a1": () => [500, { detail: "x" }] });
    await userEvent.click(await screen.findByRole("button", { name: /14:00 Reunião do projeto IE/ }));

    await userEvent.click(within(screen.getByRole("region", { name: "Compromisso selecionado" })).getByRole("button", { name: "Confirmar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível salvar");
  });
});

describe("agenda: month and list", () => {
  it("shows the month with the appointment on its day and goes to that week on click", async () => {
    open([base]);
    await userEvent.click(await screen.findByRole("button", { name: "Mês" }));

    expect(await screen.findByText("outubro de 2026")).toBeInTheDocument();
    const cell = screen.getByRole("button", { name: /28 de outubro/ });
    expect(within(cell).getByText(/Reunião do projeto IE/)).toBeInTheDocument();
    await userEvent.click(cell);

    expect(await screen.findByText("26 de outubro a 1 de novembro de 2026")).toBeInTheDocument();
  });

  it("lists the next appointments grouped by day", async () => {
    open([base, allDay]);

    await userEvent.click(await screen.findByRole("button", { name: "Lista" }));

    const day = await screen.findByRole("region", { name: "quarta-feira, 28 de outubro" });
    expect(within(day).getByText("Reunião do projeto IE")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "quinta-feira, 29 de outubro" })).toBeInTheDocument();
  });

  it("explains a failure to load", async () => {
    open([], SOCIO, { "GET /api/v1/appointments": () => [500, { detail: "x" }] });

    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível carregar a agenda");
  });
});
