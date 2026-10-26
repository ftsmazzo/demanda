import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { AppRoutes } from "../../App";
import type { Appointment, Me } from "../../api/types";
import { COLABORADOR, SOCIO, makeBoard, makeDetail } from "../../test/fixtures";
import { renderApp, type Handlers } from "../../test/utils";

const inDays = (days: number, hour = 17) => {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() + days);
  date.setUTCHours(hour, 0, 0, 0);
  return date.toISOString();
};

const reuniao: Appointment = {
  id: "a1",
  title: "Vamos marcar uma reunião para definir o projeto IE",
  starts_at: inDays(2),
  all_day: false,
  status: "proposed",
  demand_id: "d1",
  sector: "societario",
  contact: { id: "c1", name: "Poli", phone: "5511999990101", kind: "cliente", priority: false },
};
const confirmada: Appointment = {
  ...reuniao,
  id: "a2",
  title: "Visita ao cliente",
  status: "confirmed",
  all_day: true,
  contact: null,
};

function open(list: Appointment[], me: Me = SOCIO, extra: Handlers = {}) {
  return renderApp(<AppRoutes />, {
    route: "/agenda",
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

const patchedBody = (calls: { key: string; body: unknown }[], key: string) =>
  calls.find((call) => call.key === key)?.body;

describe("agenda page", () => {
  it("lists upcoming appointments by day with time, contact and state", async () => {
    open([reuniao, confirmada]);

    const first = (await screen.findByText(reuniao.title)).closest("li")!;
    expect(within(first).getByText("14:00")).toBeInTheDocument();
    expect(within(first).getByText("Poli")).toBeInTheDocument();
    expect(within(first).getByText("Proposto")).toBeInTheDocument();
    const second = screen.getByText("Visita ao cliente").closest("li")!;
    expect(within(second).getByText("O dia todo")).toBeInTheDocument();
    expect(within(second).getByText("Confirmado")).toBeInTheDocument();
  });

  it("confirms a proposed appointment", async () => {
    const key = "PATCH /api/v1/appointments/a1";
    const { calls } = open([reuniao], SOCIO, { [key]: ({ body }) => [200, { ...reuniao, ...body }] });

    await userEvent.click(await screen.findByRole("button", { name: "Confirmar" }));

    await waitFor(() => expect(patchedBody(calls, key)).toEqual({ status: "confirmed" }));
  });

  it("cancels an appointment", async () => {
    const key = "PATCH /api/v1/appointments/a2";
    const { calls } = open([confirmada], SOCIO, { [key]: ({ body }) => [200, { ...confirmada, ...body }] });

    await userEvent.click(await screen.findByRole("button", { name: "Cancelar" }));

    await waitFor(() => expect(patchedBody(calls, key)).toEqual({ status: "cancelled" }));
  });

  it("only offers Confirmar on proposed appointments", async () => {
    open([confirmada]);
    await screen.findByText("Visita ao cliente");

    expect(screen.queryByRole("button", { name: "Confirmar" })).not.toBeInTheDocument();
  });

  it("is read-only for a colaborador", async () => {
    open([reuniao], COLABORADOR);
    await screen.findByText(reuniao.title);

    expect(screen.queryByRole("button", { name: "Confirmar" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancelar" })).not.toBeInTheDocument();
  });

  it("opens the related demand when the title is clicked", async () => {
    open([reuniao]);

    await userEvent.click(await screen.findByRole("button", { name: reuniao.title }));

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("invites the first appointment when the agenda is empty", async () => {
    open([]);

    expect(await screen.findByText(/Nenhum compromisso à vista\. Quando/)).toBeInTheDocument();
  });

  it("explains a failed change", async () => {
    open([reuniao], SOCIO, { "PATCH /api/v1/appointments/a1": () => [500, { detail: "x" }] });

    await userEvent.click(await screen.findByRole("button", { name: "Confirmar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível salvar");
  });
});
