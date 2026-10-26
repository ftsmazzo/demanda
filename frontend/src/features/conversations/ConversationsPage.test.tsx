import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { AppRoutes } from "../../App";
import type { ConversationSummary, Me } from "../../api/types";
import { COLABORADOR, SOCIO, makeBoard } from "../../test/fixtures";
import { renderApp, type Handlers } from "../../test/utils";

const row = (overrides: Partial<ConversationSummary> & { name?: string | null } = {}): ConversationSummary => {
  const { name = "Poli", ...rest } = overrides;
  return {
    contact: { id: "c-1", name, phone: "5511999990101", kind: "cliente", priority: false },
    last_text: "Vamos marcar uma reunião quarta às 14",
    last_direction: "in",
    last_at: "2026-10-26T12:00:00Z",
    open_items: 0,
    waiting: 0,
    ...rest,
  };
};

function open(list: ConversationSummary[], me: Me = SOCIO, extra: Handlers = {}, route = "/conversas") {
  return renderApp(<AppRoutes />, {
    route,
    signedIn: true,
    handlers: {
      "GET /api/v1/me": () => [200, me],
      "GET /api/v1/board": () => [200, makeBoard([])],
      "GET /api/v1/conversations": () => [200, list],
      "GET /api/v1/today": () => [
        200,
        { needs_review: [], to_confirm: [], attention: [], waiting_triage: 0, counts: { open: 0, meetings_today: 0 } },
      ],
      ...extra,
    },
  });
}

describe("conversations inbox", () => {
  it("lists each contact with the last message and what came out of it", async () => {
    open([
      row({ open_items: 2, waiting: 1 }),
      row({
        name: "Mercado Bom Preço",
        last_direction: "out",
        last_text: "Combinado, até quinta",
        contact: { id: "c-2", name: "Mercado Bom Preço", phone: "5511999990102", kind: "cliente", priority: true },
      }),
    ]);

    const first = (await screen.findByText("Poli")).closest("li")!;
    expect(within(first).getByText("Vamos marcar uma reunião quarta às 14")).toBeInTheDocument();
    expect(within(first).getByText("2 itens abertos")).toBeInTheDocument();
    expect(within(first).getByText("1 na triagem")).toBeInTheDocument();
    const second = screen.getByText("Mercado Bom Preço").closest("li")!;
    expect(within(second).getByText("Você: Combinado, até quinta")).toBeInTheDocument();
    expect(within(second).getByText("Prioritário")).toBeInTheDocument();
  });

  it("opens the whole conversation of a contact", async () => {
    open([row()]);

    const link = await screen.findByRole("link", { name: /Poli/ });

    expect(link).toHaveAttribute("href", "/contatos/c-1/conversa");
  });

  it("searches on the server and filters the ones waiting for triage", async () => {
    const { calls } = open([row()]);
    await screen.findByText("Poli");

    await userEvent.type(screen.getByRole("searchbox", { name: "Buscar conversa" }), "poli");
    await userEvent.click(screen.getByRole("button", { name: "Na triagem" }));

    await waitFor(() => {
      const last = calls.filter((call) => call.key === "GET /api/v1/conversations").at(-1)!;
      expect(last.url.searchParams.get("q")).toBe("poli");
      expect(last.url.searchParams.get("waiting")).toBe("true");
    });
    expect(screen.getByRole("button", { name: "Na triagem" })).toHaveAttribute("aria-pressed", "true");
  });

  it("starts filtered when it comes from the triage banner", async () => {
    const { calls } = open([row({ waiting: 2 })], SOCIO, {}, "/conversas?triagem=1");

    await screen.findByText("Poli");

    const first = calls.find((call) => call.key === "GET /api/v1/conversations")!;
    expect(first.url.searchParams.get("waiting")).toBe("true");
  });

  it("says what to expect when there is nothing yet", async () => {
    open([]);

    expect(await screen.findByText(/Nenhuma conversa ainda/)).toBeInTheDocument();
  });

  it("explains a failure and is not available to a colaborador", async () => {
    open([], SOCIO, { "GET /api/v1/conversations": () => [500, { detail: "x" }] });
    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível carregar");
  });

  it("sends a colaborador back to the start", async () => {
    open([row()], COLABORADOR);

    expect(await screen.findByRole("heading", { name: "Hoje" })).toBeInTheDocument();
  });
});
