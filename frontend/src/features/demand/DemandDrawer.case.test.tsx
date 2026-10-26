import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { CaseEvent } from "../../api/types";
import { COLABORADOR, GESTOR, SOCIO } from "../../test/fixtures";
import { detail, drawer, setup } from "./testkit";

const review = (reason: string, data: Record<string, unknown> = {}): CaseEvent => ({
  id: "ev-r",
  actor: "ai",
  kind: "review",
  data: { reason, ...data },
  created_at: "2026-10-26T12:05:00Z",
});

const created: CaseEvent = {
  id: "ev-1",
  actor: "ai",
  kind: "created",
  data: {},
  created_at: "2026-10-26T12:00:00Z",
};

const patched = (calls: { key: string; body: unknown }[], key: string) =>
  calls.find((call) => call.key === key)?.body;

describe("case drawer", () => {
  it("opens with the summary and the next step before anything else", async () => {
    setup(SOCIO, detail({ summary: "Ana pediu férias para dezembro.", next_step: "Lançar as férias no RH." }));

    const box = await drawer();

    expect(within(box).getByText("Ana pediu férias para dezembro.")).toBeInTheDocument();
    expect(within(box).getByText("Próximo passo")).toBeInTheDocument();
    expect(within(box).getByText("Lançar as férias no RH.")).toBeInTheDocument();
  });

  it("shows the history in plain words with who did each step", async () => {
    setup(SOCIO, detail({ events: [created, review("confirmar agrupamento")] }));

    const box = await drawer();

    const history = within(box).getByRole("region", { name: /Histórico/ });
    expect(within(history).getByText("Caso aberto")).toBeInTheDocument();
    expect(within(history).getByText("Marcado para revisão: confirmar agrupamento")).toBeInTheDocument();
    expect(within(history).getAllByText("IA")).toHaveLength(2);
  });

  it("lists the appointments of the case with day, time and state", async () => {
    setup(
      SOCIO,
      detail({
        appointments: [
          { id: "a1", title: "Reunião do projeto IE", starts_at: "2026-10-28T17:00:00Z", all_day: false, status: "proposed" },
        ],
      }),
    );

    const box = await drawer();

    const section = within(box).getByRole("region", { name: /Compromissos/ });
    expect(within(section).getByText("quarta-feira, 28/10 às 14:00")).toBeInTheDocument();
    expect(within(section).getByText("Proposto")).toBeInTheDocument();
  });

  it("links to the whole conversation with the contact", async () => {
    setup(SOCIO, detail());

    const box = await drawer();

    expect(within(box).getByRole("link", { name: "Ver a conversa inteira" })).toHaveAttribute(
      "href",
      "/contatos/c-1/conversa",
    );
  });

  it("asks to confirm an uncertain grouping and merges into the earlier case", async () => {
    const candidate = "d-antigo";
    const { calls } = setup(
      SOCIO,
      detail({ needs_review: true, review_reason: "confirmar agrupamento", events: [review("confirmar agrupamento", { candidate })] }),
      {
        "POST /api/v1/demands/d1/merge": () => [200, detail({ id: candidate, title: "Caso antigo" })],
        [`GET /api/v1/demands/${candidate}`]: () => [200, detail({ id: candidate, title: "Caso antigo" })],
      },
    );
    const box = await drawer();

    expect(within(box).getByRole("alert")).toHaveTextContent("não teve certeza");
    await userEvent.click(within(box).getByRole("button", { name: "Juntar ao caso anterior" }));

    await waitFor(() => expect(patched(calls, "POST /api/v1/demands/d1/merge")).toEqual({ into: candidate }));
    expect(await screen.findByRole("heading", { name: "Caso antigo" })).toBeInTheDocument();
  });

  it("keeps the case separate and clears the flag", async () => {
    const { calls } = setup(
      SOCIO,
      detail({ needs_review: true, review_reason: "confirmar agrupamento", events: [review("confirmar agrupamento", { candidate: "x" })] }),
      { "PATCH /api/v1/demands/d1": ({ body }) => [200, detail({ ...body, needs_review: false })] },
    );
    const box = await drawer();

    await userEvent.click(within(box).getByRole("button", { name: "É um caso separado" }));

    await waitFor(() => expect(patched(calls, "PATCH /api/v1/demands/d1")).toEqual({ needs_review: false }));
  });

  it("applies a suggested new time to the appointment and clears the flag", async () => {
    const proposal: CaseEvent = {
      id: "ev-p",
      actor: "ai",
      kind: "proposal",
      data: { appointment_id: "a1", proposed: { starts_at: "2026-10-29T13:00:00Z", all_day: false } },
      created_at: "2026-10-26T12:10:00Z",
    };
    const { calls } = setup(
      SOCIO,
      detail({
        needs_review: true,
        review_reason: "possivel remarcacao",
        events: [proposal],
        appointments: [{ id: "a1", title: "Reunião", starts_at: "2026-10-28T17:00:00Z", all_day: false, status: "confirmed" }],
      }),
      {
        "PATCH /api/v1/appointments/a1": () => [200, {}],
        "PATCH /api/v1/demands/d1": ({ body }) => [200, detail({ ...body, needs_review: false })],
      },
    );
    const box = await drawer();

    expect(within(box).getByRole("alert")).toHaveTextContent("quinta-feira, 29/10 às 10:00");
    await userEvent.click(within(box).getByRole("button", { name: "Aplicar o novo horário" }));

    await waitFor(() =>
      expect(patched(calls, "PATCH /api/v1/appointments/a1")).toEqual({
        starts_at: "2026-10-29T13:00:00Z",
        all_day: false,
        status: "proposed",
      }),
    );
    await waitFor(() => expect(patched(calls, "PATCH /api/v1/demands/d1")).toEqual({ needs_review: false }));
  });

  it("only managers get the review buttons", async () => {
    const flagged = detail({ needs_review: true, review_reason: "classificacao incerta", assignee: { id: "u-3", name: "Bruno Costa" } });
    setup(COLABORADOR, flagged);

    const box = await drawer();

    expect(within(box).getByRole("alert")).toHaveTextContent("dúvida");
    expect(within(box).queryByRole("button", { name: "Está certo" })).not.toBeInTheDocument();
  });

  it("a gestor sees the buttons too", async () => {
    setup(GESTOR, detail({ needs_review: true, review_reason: "classificacao incerta" }));

    const box = await drawer();

    expect(within(box).getByRole("button", { name: "Está certo" })).toBeInTheDocument();
  });
});
