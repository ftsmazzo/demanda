import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { AppRoutes } from "../../App";
import type { Appointment, Me, TodayData } from "../../api/types";
import { COLABORADOR, SOCIO, makeBoard, makeCard, makeDetail } from "../../test/fixtures";
import { renderApp, type Handlers } from "../../test/utils";

const inDays = (days: number) => new Date(Date.now() + days * 86_400_000).toISOString();

const meeting: Appointment = {
  id: "a1",
  title: "Reunião do projeto IE",
  starts_at: inDays(2),
  all_day: false,
  status: "proposed",
  demand_id: "d9",
  sector: "societario",
  contact: { id: "c1", name: "Poli", phone: "5511999990101", kind: "cliente", priority: false },
};

const empty = (): TodayData => ({
  needs_review: [],
  to_confirm: [],
  attention: [],
  waiting_triage: 0,
  counts: { open: 0, meetings_today: 0 },
});

function open(data: Partial<TodayData>, me: Me = SOCIO, extra: Handlers = {}) {
  return renderApp(<AppRoutes />, {
    signedIn: true,
    handlers: {
      "GET /api/v1/me": () => [200, me],
      "GET /api/v1/today": () => [200, { ...empty(), ...data }],
      "GET /api/v1/board": () => [200, makeBoard([])],
      "GET /api/v1/demands/c9": () => [200, makeDetail({ id: "c9", title: "Item para revisar" })],
      ...extra,
    },
  });
}

describe("today page", () => {
  it("opens by saying how many things wait for a decision", async () => {
    open({
      needs_review: [makeCard({ id: "c9", title: "Item para revisar", needs_review: true, review_reason: "confirmar agrupamento" })],
      to_confirm: [meeting],
    });

    expect(await screen.findByText("2 itens esperam a sua decisão.")).toBeInTheDocument();
  });

  it("shows the appointments to confirm and confirms one in place", async () => {
    const key = "PATCH /api/v1/appointments/a1";
    const { calls } = open({ to_confirm: [meeting] }, SOCIO, { [key]: ({ body }) => [200, { ...meeting, ...body }] });

    const section = await screen.findByRole("region", { name: "Compromissos para confirmar" });
    expect(within(section).getByText("Reunião do projeto IE")).toBeInTheDocument();
    await userEvent.click(within(section).getByRole("button", { name: "Confirmar" }));

    await waitFor(() => expect(calls.find((call) => call.key === key)?.body).toEqual({ status: "confirmed" }));
  });

  it("lists the items the AI was unsure about and opens one", async () => {
    open({
      needs_review: [makeCard({ id: "c9", title: "Item para revisar", needs_review: true, review_reason: "confirmar agrupamento" })],
    });

    const section = await screen.findByRole("region", { name: "A IA ficou em dúvida" });
    await userEvent.click(within(section).getByRole("button", { name: /Item para revisar/ }));

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("highlights what asks for attention, priority clients included", async () => {
    open({
      attention: [
        makeCard({ title: "Crítica parada", urgency: "critica", idle_hours: 50 }),
        makeCard({
          title: "Do cliente prioritário",
          idle_hours: 30,
          contact: { id: "c2", name: "Mercado", phone: "5511999990102", kind: "cliente", priority: true },
        }),
      ],
    });

    const section = await screen.findByRole("region", { name: "Pedem atenção" });

    expect(within(section).getByText("Crítica parada")).toBeInTheDocument();
    expect(within(section).getByText("Prioritário")).toBeInTheDocument();
  });

  it("points to the messages still waiting for triage", async () => {
    open({ waiting_triage: 3 });

    const link = await screen.findByRole("link", { name: /3 mensagens na triagem/ });

    expect(link).toHaveAttribute("href", "/conversas?triagem=1");
  });

  it("says everything is fine when nothing is waiting", async () => {
    open({});

    expect(await screen.findByText("Tudo em ordem por aqui.")).toBeInTheDocument();
  });

  it("gives a colaborador the same page without decisions to take", async () => {
    open({ to_confirm: [meeting] }, COLABORADOR);

    const section = await screen.findByRole("region", { name: "Compromissos para confirmar" });

    expect(within(section).queryByRole("button", { name: "Confirmar" })).not.toBeInTheDocument();
  });

  it("explains a failure and can retry", async () => {
    open({}, SOCIO, { "GET /api/v1/today": () => [500, { detail: "x" }] });

    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível carregar");
  });
});
