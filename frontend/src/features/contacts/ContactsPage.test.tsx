import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { AppRoutes } from "../../App";
import type { ContactRef } from "../../api/types";
import { COLABORADOR, SOCIO } from "../../test/fixtures";
import { renderApp, type Handlers } from "../../test/utils";

const padaria: ContactRef = { id: "c-1", name: "Padaria Estrela", phone: "5511999990101", kind: "cliente", priority: false };
const semNome: ContactRef = { id: "c-2", name: null, phone: "5511999990102", kind: "desconhecido", priority: false };

function open(extra: Handlers = {}, me = SOCIO) {
  return renderApp(<AppRoutes />, {
    route: "/contatos",
    signedIn: true,
    handlers: {
      "GET /api/v1/me": () => [200, me],
      "GET /api/v1/board": () => [200, { columns: [] }],
      "GET /api/v1/contacts": () => [200, [padaria, semNome]],
      ...extra,
    },
  });
}

describe("contacts page", () => {
  it("lists contacts with name, phone and kind", async () => {
    open();

    const row = (await screen.findByText("Padaria Estrela")).closest("li")!;
    expect(within(row).getByText("(11) 99999-0101")).toBeInTheDocument();
    expect(within(row).getByLabelText("Tipo de Padaria Estrela")).toHaveValue("cliente");
    expect(screen.getByText("Sem nome")).toBeInTheDocument();
  });

  it("searches by text and filters by kind on the server", async () => {
    const { calls } = open();
    await screen.findByText("Padaria Estrela");

    await userEvent.type(screen.getByRole("searchbox", { name: "Buscar contato" }), "padar");
    await userEvent.selectOptions(screen.getByLabelText("Filtrar por tipo"), "cliente");

    await waitFor(() => {
      const last = calls.filter((call) => call.key === "GET /api/v1/contacts").at(-1)!;
      expect(last.url.searchParams.get("q")).toBe("padar");
      expect(last.url.searchParams.get("kind")).toBe("cliente");
    });
  });

  it("changes the kind of a contact", async () => {
    const { calls } = open({
      "PATCH /api/v1/contacts/c-2": ({ body }) => [200, { ...semNome, ...body }],
    });
    const select = await screen.findByLabelText("Tipo de contato sem nome (final 0102)");

    await userEvent.selectOptions(select, "fornecedor");

    await waitFor(() =>
      expect(calls.find((call) => call.key === "PATCH /api/v1/contacts/c-2")?.body).toEqual({ kind: "fornecedor" }),
    );
  });

  it("renames a contact", async () => {
    const { calls } = open({
      "PATCH /api/v1/contacts/c-2": ({ body }) => [200, { ...semNome, ...body }],
    });
    await userEvent.click(await screen.findByRole("button", { name: "Dar nome a contato sem nome (final 0102)" }));

    const field = screen.getByLabelText("Nome do contato");
    await userEvent.type(field, "  Oficina do Zé {Enter}");

    await waitFor(() =>
      expect(calls.find((call) => call.key === "PATCH /api/v1/contacts/c-2")?.body).toEqual({ name: "Oficina do Zé" }),
    );
    await waitFor(() => expect(screen.queryByLabelText("Nome do contato")).not.toBeInTheDocument());
  });

  it("leaves a name unchanged on Escape", async () => {
    const { calls } = open();
    await userEvent.click(await screen.findByRole("button", { name: "Renomear Padaria Estrela" }));

    await userEvent.type(screen.getByLabelText("Nome do contato"), "x{Escape}");

    expect(screen.queryByLabelText("Nome do contato")).not.toBeInTheDocument();
    expect(calls.some((call) => call.key.startsWith("PATCH"))).toBe(false);
  });

  it("explains a failed change", async () => {
    open({ "PATCH /api/v1/contacts/c-1": () => [500, { detail: "erro" }] });

    await userEvent.selectOptions(await screen.findByLabelText("Tipo de Padaria Estrela"), "fornecedor");

    expect(await screen.findByRole("alert")).toHaveTextContent("Não foi possível salvar");
  });

  it("says so when nothing matches", async () => {
    open({ "GET /api/v1/contacts": () => [200, []] });

    expect(await screen.findByText("Nenhum contato encontrado.")).toBeInTheDocument();
  });

  it("is not available to a collaborator", async () => {
    open({}, COLABORADOR);

    await waitFor(() => expect(screen.queryByRole("heading", { name: "Contatos" })).not.toBeInTheDocument());
  });

  it("links each contact to the whole conversation", async () => {
    open();

    const row = (await screen.findByText("Padaria Estrela")).closest("li")!;

    expect(within(row).getByRole("link", { name: "Ver conversa de Padaria Estrela" })).toHaveAttribute(
      "href",
      "/contatos/c-1/conversa",
    );
  });

  it("marks and unmarks a client as priority", async () => {
    const key = "PATCH /api/v1/contacts/c-1";
    const { calls } = open({ [key]: ({ body }) => [200, { ...padaria, ...body }] });

    const star = await screen.findByRole("button", { name: "Marcar Padaria Estrela como prioritário" });
    expect(star).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(star);

    await waitFor(() => expect(calls.find((call) => call.key === key)?.body).toEqual({ priority: true }));
  });

  it("shows a priority client as marked", async () => {
    open({ "GET /api/v1/contacts": () => [200, [{ ...padaria, priority: true }]] });

    const star = await screen.findByRole("button", { name: "Tirar a prioridade de Padaria Estrela" });

    expect(star).toHaveAttribute("aria-pressed", "true");
  });
});
