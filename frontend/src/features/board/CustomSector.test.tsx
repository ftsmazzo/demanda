import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { AppRoutes } from "../../App";
import type { SectorInfo } from "../../api/types";
import { SOCIO, USERS, makeBoard, makeCard } from "../../test/fixtures";
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
  sector("juridico", "Jurídico Trabalhista", { color: "#336699" }),
  sector("velho", "Setor antigo", { active: false }),
];

function open(extra: Handlers = {}, cards = [makeCard({ title: "Revisar contrato", sector: "juridico" })]) {
  return renderApp(<AppRoutes />, {
    route: "/quadro",
    signedIn: true,
    handlers: {
      "GET /api/v1/me": () => [200, SOCIO],
      "GET /api/v1/board": () => [200, makeBoard(cards)],
      "GET /api/v1/users": () => [200, USERS],
      "GET /api/v1/sectors": () => [200, OFFICE],
      ...extra,
    },
  });
}

describe("sectors that the office defined", () => {
  it("shows the office's own name and color on a card", async () => {
    const { calls } = open();

    const card = (await screen.findByText("Revisar contrato")).closest("button")!;

    expect(await within(card).findByText("Jurídico Trabalhista")).toBeInTheDocument();
    expect(within(card).getByText("Jurídico Trabalhista")).toHaveStyle({ "--dot": "#336699" });
    expect(
      calls.some((c) => c.key === "GET /api/v1/sectors" && c.url.searchParams.get("include_inactive") === "true"),
    ).toBe(true);
  });

  it("falls back to the standard names when the list is unavailable", async () => {
    open({ "GET /api/v1/sectors": () => [500, { detail: "x" }] }, [makeCard({ title: "Guia", sector: "fiscal" })]);

    const card = (await screen.findByText("Guia")).closest("button")!;

    expect(within(card).getByText("Fiscal")).toBeInTheDocument();
  });

  it("names a turned-off sector on old cards but does not offer it", async () => {
    open({}, [makeCard({ title: "Caso antigo", sector: "velho" })]);

    const card = (await screen.findByText("Caso antigo")).closest("button")!;
    expect(await within(card).findByText("Setor antigo")).toBeInTheDocument();
    const filter = screen.getByRole("combobox", { name: "Filtrar por setor" });

    expect(within(filter).getByRole("option", { name: "Jurídico Trabalhista" })).toBeInTheDocument();
    expect(within(filter).queryByRole("option", { name: "Setor antigo" })).not.toBeInTheDocument();
  });

  it("offers the new sector when starting a demand", async () => {
    open();
    await userEvent.click(await screen.findByRole("button", { name: /Nova demanda/ }));

    const dialog = await screen.findByRole("dialog");
    const select = within(dialog).getByLabelText("Setor");

    expect(within(select).getByRole("option", { name: "Jurídico Trabalhista" })).toBeInTheDocument();
    expect(within(select).queryByRole("option", { name: "Triagem" })).not.toBeInTheDocument();
  });
});
