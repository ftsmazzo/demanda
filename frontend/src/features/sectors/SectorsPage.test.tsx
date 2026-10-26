import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { AppRoutes } from "../../App";
import type { Me, SectorInfo } from "../../api/types";
import { GESTOR, SOCIO, makeBoard } from "../../test/fixtures";
import { renderApp, type Handlers } from "../../test/utils";

const sector = (slug: string, label: string, extra: Partial<SectorInfo> = {}): SectorInfo => ({
  slug,
  label,
  color: "#112233",
  system: false,
  active: true,
  ...extra,
});
const OFFICE = [
  sector("triagem", "Triagem", { system: true }),
  sector("fiscal", "Fiscal"),
  sector("juridico", "Jurídico"),
  sector("velho", "Setor antigo", { active: false }),
];

function open(me: Me = SOCIO, extra: Handlers = {}, route = "/setores") {
  return renderApp(<AppRoutes />, {
    route,
    signedIn: true,
    handlers: {
      "GET /api/v1/me": () => [200, me],
      "GET /api/v1/board": () => [200, makeBoard([])],
      "GET /api/v1/sectors": () => [200, OFFICE],
      ...extra,
    },
  });
}

const sent = (calls: { key: string; body: unknown }[], key: string) => calls.find((c) => c.key === key)?.body;

describe("sectors page", () => {
  it("lists every sector with its state, system ones without a switch", async () => {
    open();

    const list = await screen.findByRole("list", { name: "Setores" });

    expect(within(list).getByDisplayValue("Fiscal")).toBeInTheDocument();
    expect(within(list).getByText("Desligado")).toBeInTheDocument();
    expect(within(list).getByText("Do sistema")).toBeInTheDocument();
    expect(within(list).queryByRole("button", { name: "Desligar Triagem" })).not.toBeInTheDocument();
    expect(within(list).getByRole("button", { name: "Desligar Jurídico" })).toBeInTheDocument();
    expect(within(list).getByRole("button", { name: "Ligar Setor antigo" })).toBeInTheDocument();
  });

  it("creates a sector from its name", async () => {
    const key = "POST /api/v1/sectors";
    const { calls } = open(SOCIO, { [key]: ({ body }) => [201, sector("novo", body.label)] });

    await userEvent.type(await screen.findByLabelText("Nome do novo setor"), "Recursos humanos");
    await userEvent.click(screen.getByRole("button", { name: "Adicionar setor" }));

    await waitFor(() => expect(sent(calls, key)).toEqual({ label: "Recursos humanos" }));
    await waitFor(() => expect(screen.getByLabelText("Nome do novo setor")).toHaveValue(""));
  });

  it("does not send an empty name", async () => {
    const { calls } = open();

    await userEvent.click(await screen.findByRole("button", { name: "Adicionar setor" }));

    expect(calls.some((c) => c.key === "POST /api/v1/sectors")).toBe(false);
    expect(screen.getByText("Escreva o nome do setor.")).toBeInTheDocument();
  });

  it("renames on Enter and only when the name changed", async () => {
    const key = "PATCH /api/v1/sectors/juridico";
    const { calls } = open(SOCIO, { [key]: ({ body }) => [200, sector("juridico", body.label)] });
    const field = await screen.findByLabelText("Nome de Jurídico");

    await userEvent.type(field, "{Enter}");
    expect(calls.some((c) => c.key === key)).toBe(false);
    await userEvent.clear(field);
    await userEvent.type(field, "Jurídico Trabalhista{Enter}");

    await waitFor(() => expect(sent(calls, key)).toEqual({ label: "Jurídico Trabalhista" }));
  });

  it("changes the color", async () => {
    const key = "PATCH /api/v1/sectors/fiscal";
    const { calls } = open(SOCIO, { [key]: ({ body }) => [200, sector("fiscal", "Fiscal", { color: body.color })] });

    fireEvent.change(await screen.findByLabelText("Cor de Fiscal"), { target: { value: "#abcdef" } });

    await waitFor(() => expect(sent(calls, key)).toEqual({ color: "#abcdef" }));
  });

  it("turns a sector off and back on", async () => {
    const off = "PATCH /api/v1/sectors/juridico";
    const on = "PATCH /api/v1/sectors/velho";
    const { calls } = open(SOCIO, {
      [off]: () => [200, sector("juridico", "Jurídico", { active: false })],
      [on]: () => [200, sector("velho", "Setor antigo")],
    });

    await userEvent.click(await screen.findByRole("button", { name: "Desligar Jurídico" }));
    await waitFor(() => expect(sent(calls, off)).toEqual({ active: false }));
    await userEvent.click(screen.getByRole("button", { name: "Ligar Setor antigo" }));

    await waitFor(() => expect(sent(calls, on)).toEqual({ active: true }));
  });

  it("explains a repeated name", async () => {
    open(SOCIO, { "POST /api/v1/sectors": () => [409, { detail: "x" }] });

    await userEvent.type(await screen.findByLabelText("Nome do novo setor"), "Fiscal");
    await userEvent.click(screen.getByRole("button", { name: "Adicionar setor" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Já existe um setor com esse nome.");
  });

  it("is for socios only", async () => {
    open(GESTOR);

    expect(await screen.findByRole("link", { name: "Hoje", current: "page" })).toBeInTheDocument();
  });

  it("is reachable from the sócio panel", async () => {
    open(SOCIO, {}, "/painel");

    expect(await screen.findByRole("link", { name: "Setores do escritório" })).toHaveAttribute("href", "/setores");
  });
});
