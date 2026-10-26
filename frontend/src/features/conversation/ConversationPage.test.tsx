import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { AppRoutes } from "../../App";
import type { Conversation } from "../../api/types";
import { COLABORADOR, SOCIO, makeBoard, makeCard, makeDetail } from "../../test/fixtures";
import { renderApp, type Handlers } from "../../test/utils";

const poli = { id: "c-1", name: "Poli", phone: "5511999990101", kind: "cliente" as const, priority: false };

const conversation = (): Conversation => ({
  contact: poli,
  cases: [
    makeCard({ id: "d1", title: "Reunião do projeto IE", summary: "Poli quer definir o projeto IE.", status: "em_andamento" }),
    makeCard({ id: "d2", title: "Guia do DAS", summary: "Pediu a guia de outubro." }),
  ],
  messages: [
    { id: "m1", direction: "in", text: "Vamos marcar uma reunião quarta às 14", type: "conversation", sent_at: "2026-10-26T12:00:00Z", demand_id: "d1" },
    { id: "m2", direction: "out", text: "Combinado, Poli.", type: "conversation", sent_at: "2026-10-26T12:05:00Z", demand_id: "d1" },
    { id: "m3", direction: "in", text: "E a guia do DAS?", type: "conversation", sent_at: "2026-10-26T13:00:00Z", demand_id: "d2" },
    { id: "m4", direction: "in", text: "obrigado", type: "conversation", sent_at: "2026-10-26T13:10:00Z", demand_id: null },
  ],
});

function open(extra: Handlers = {}, me = SOCIO) {
  return renderApp(<AppRoutes />, {
    route: "/contatos/c-1/conversa",
    signedIn: true,
    handlers: {
      "GET /api/v1/me": () => [200, me],
      "GET /api/v1/board": () => [200, makeBoard([])],
      "GET /api/v1/contacts/c-1/conversation": () => [200, conversation()],
      "GET /api/v1/demands/d1": () => [200, makeDetail({ id: "d1", title: "Reunião do projeto IE" })],
      ...extra,
    },
  });
}

describe("conversation page", () => {
  it("shows who the contact is and the whole thread with both sides apart", async () => {
    open();

    expect(await screen.findByRole("heading", { name: "Poli" })).toBeInTheDocument();
    const thread = screen.getByRole("log", { name: "Conversa" });
    expect(within(thread).getByText("Vamos marcar uma reunião quarta às 14")).toBeInTheDocument();
    const reply = within(thread).getByText("Combinado, Poli.").closest(".msg")!;
    expect(reply).toHaveClass("out");
    expect(within(thread).getByText("E a guia do DAS?").closest(".msg")).not.toHaveClass("out");
  });

  it("names the case when the thread changes subject and marks loose messages", async () => {
    open();

    const thread = await screen.findByRole("log", { name: "Conversa" });

    expect(within(thread).getAllByText("Reunião do projeto IE")).toHaveLength(1);
    expect(within(thread).getByText("Guia do DAS")).toBeInTheDocument();
    expect(within(thread).getByText("Sem caso")).toBeInTheDocument();
  });

  it("lists the cases with their summaries and opens one", async () => {
    open();

    const list = await screen.findByRole("region", { name: "Casos deste contato" });
    expect(within(list).getByText("Poli quer definir o projeto IE.")).toBeInTheDocument();
    await userEvent.click(within(list).getByRole("button", { name: /Reunião do projeto IE/ }));

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });

  it("says what came out of the conversation and of which kind", async () => {
    open({
      "GET /api/v1/contacts/c-1/conversation": () => [
        200,
        { ...conversation(), cases: [makeCard({ id: "d3", title: "Cobrar extratos", kind: "cobranca" })] },
      ],
    });

    const list = await screen.findByRole("region", { name: "Casos deste contato" });

    expect(within(list).getByRole("heading", { name: /O que saiu desta conversa/ })).toBeInTheDocument();
    expect(within(list).getByText("Cobrança")).toBeInTheDocument();
  });

  it("explains a conversation that is gone or off limits", async () => {
    open({ "GET /api/v1/contacts/c-1/conversation": () => [404, { detail: "x" }] });

    expect(await screen.findByText("Esta conversa não existe ou você não tem acesso a ela.")).toBeInTheDocument();
  });

  it("is not available to a colaborador", async () => {
    open({}, COLABORADOR);

    expect(await screen.findByRole("link", { name: "Hoje", current: "page" })).toBeInTheDocument();
    expect(screen.queryByRole("log", { name: "Conversa" })).not.toBeInTheDocument();
  });

  it("links back to the contacts list", async () => {
    open();

    expect(await screen.findByRole("link", { name: "Voltar para os contatos" })).toHaveAttribute("href", "/contatos");
  });
});
