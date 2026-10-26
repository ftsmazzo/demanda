import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { AppRoutes } from "../../App";
import type { Me } from "../../api/types";
import { GESTOR, SOCIO, USERS, makeBoard, makeDetail } from "../../test/fixtures";
import { renderApp, type Handlers } from "../../test/utils";

function handlersFor(me: Me, extra: Handlers = {}): Handlers {
  return {
    "GET /api/v1/me": () => [200, me],
    "GET /api/v1/board": () => [200, makeBoard([])],
    "GET /api/v1/users": () => [200, USERS],
    ...extra,
  };
}

async function openDialog(me: Me, extra: Handlers = {}) {
  const view = renderApp(<AppRoutes />, { route: "/quadro", signedIn: true, handlers: handlersFor(me, extra) });
  await userEvent.click(await screen.findByRole("button", { name: "Nova demanda" }));
  const box = await screen.findByRole("dialog", { name: "Nova demanda" });
  return { ...view, box };
}

describe("new demand dialog", () => {
  it("creates the demand with the chosen fields and opens it", async () => {
    const created = makeDetail({ id: "novo-1", title: "Conferir o parcelamento" });
    const { box, calls } = await openDialog(SOCIO, {
      "POST /api/v1/demands": () => [201, created],
      "GET /api/v1/demands/novo-1": () => [200, created],
    });

    await userEvent.type(within(box).getByLabelText("O que precisa ser feito"), "  Conferir o parcelamento ");
    await userEvent.selectOptions(within(box).getByLabelText("Setor"), "fiscal");
    await userEvent.click(within(box).getByRole("button", { name: "Alta" }));
    await userEvent.selectOptions(within(box).getByLabelText("Responsável"), "u-3");
    await userEvent.click(within(box).getByRole("button", { name: "Criar demanda" }));

    await waitFor(() => expect(calls.some((call) => call.key === "POST /api/v1/demands")).toBe(true));
    const post = calls.find((call) => call.key === "POST /api/v1/demands");
    expect(post?.body).toEqual({
      title: "Conferir o parcelamento",
      sector: "fiscal",
      urgency: "alta",
      assignee_id: "u-3",
      due_date: null,
    });
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Nova demanda" })).not.toBeInTheDocument());
    expect(await screen.findByRole("heading", { name: "Conferir o parcelamento" })).toBeInTheDocument();
  });

  it("does not send an empty title", async () => {
    const { box, calls } = await openDialog(SOCIO);

    await userEvent.click(within(box).getByRole("button", { name: "Criar demanda" }));

    expect(await within(box).findByText("Escreva o que precisa ser feito.")).toBeInTheDocument();
    expect(calls.some((call) => call.key === "POST /api/v1/demands")).toBe(false);
  });

  it("offers a manager only the sectors they work in", async () => {
    const { box } = await openDialog(GESTOR);

    const options = within(within(box).getByLabelText("Setor")).getAllByRole("option");

    expect(options.map((option) => option.textContent)).toEqual(["Fiscal"]);
  });

  it("explains a refusal and keeps what was typed", async () => {
    const { box } = await openDialog(SOCIO, {
      "POST /api/v1/demands": () => [403, { detail: "sem permissao" }],
    });

    await userEvent.type(within(box).getByLabelText("O que precisa ser feito"), "Algo");
    await userEvent.click(within(box).getByRole("button", { name: "Criar demanda" }));

    expect(await within(box).findByRole("alert")).toHaveTextContent("Você não tem permissão");
    expect(within(box).getByLabelText("O que precisa ser feito")).toHaveValue("Algo");
  });

  it("closes with Escape and with Cancelar", async () => {
    const { box } = await openDialog(SOCIO);

    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Nova demanda" })).not.toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Nova demanda" }));
    await userEvent.click(within(await screen.findByRole("dialog", { name: "Nova demanda" })).getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByRole("dialog", { name: "Nova demanda" })).not.toBeInTheDocument();
    expect(box).toBeDefined();
  });
});
