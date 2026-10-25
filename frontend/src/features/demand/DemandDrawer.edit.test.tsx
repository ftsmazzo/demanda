import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { COLABORADOR, SOCIO } from "../../test/fixtures";
import { detail, drawer, setup } from "./testkit";

const patched = (calls: { key: string; body: unknown }[]) =>
  calls.filter((c) => c.key === "PATCH /api/v1/demands/d1").map((c) => c.body);

describe("demand drawer: editing", () => {
  it("changes the status and refreshes the board", async () => {
    const user = userEvent.setup({ delay: null });
    const { calls } = setup(SOCIO, detail(), {
      "PATCH /api/v1/demands/d1": ({ body }) => [200, detail({ status: body.status })],
    });

    const box = await drawer();
    await user.click(within(box).getByRole("button", { name: "Aguardando" }));

    await waitFor(() =>
      expect(within(box).getByRole("button", { name: "Aguardando" })).toHaveAttribute("aria-pressed", "true"),
    );
    expect(patched(calls)).toEqual([{ status: "aguardando" }]);
    await waitFor(() => expect(calls.filter((c) => c.key === "GET /api/v1/board").length).toBeGreaterThan(1));
  });

  it("reassigns, including back to nobody", async () => {
    const user = userEvent.setup({ delay: null });
    const { calls } = setup(SOCIO, detail(), { "PATCH /api/v1/demands/d1": () => [200, detail()] });

    const box = await drawer();
    await user.selectOptions(within(box).getByLabelText("Responsável"), "Rafael Souza");
    await user.selectOptions(within(box).getByLabelText("Responsável"), "Sem responsável");

    expect(patched(calls)).toEqual([{ assignee_id: "u-2" }, { assignee_id: null }]);
  });

  it("changes sector, urgency and due date", async () => {
    const user = userEvent.setup({ delay: null });
    const { calls } = setup(SOCIO, detail(), { "PATCH /api/v1/demands/d1": () => [200, detail()] });

    const box = await drawer();
    await user.selectOptions(within(box).getByLabelText("Setor"), "Fiscal");
    await user.selectOptions(within(box).getByLabelText("Urgência"), "Alta");
    await user.type(within(box).getByLabelText("Prazo"), "2026-12-31");

    expect(patched(calls)).toContainEqual({ sector: "fiscal" });
    expect(patched(calls)).toContainEqual({ urgency: "alta" });
    expect(patched(calls)).toContainEqual({ due_date: "2026-12-31" });
  });

  it("shows why a change was refused", async () => {
    const user = userEvent.setup({ delay: null });
    setup(SOCIO, detail(), {
      "PATCH /api/v1/demands/d1": () => [403, { detail: "sem permissao para mover para este setor" }],
    });

    const box = await drawer();
    await user.selectOptions(within(box).getByLabelText("Setor"), "Fiscal");

    expect(await within(box).findByRole("alert")).toHaveTextContent("Você não tem permissão para fazer essa alteração.");
  });

  it("lets a colaborador move only the status", async () => {
    setup(COLABORADOR);

    const box = await drawer();
    expect(within(box).getByRole("button", { name: "Aguardando" })).toBeEnabled();
    expect(within(box).queryByLabelText("Responsável")).not.toBeInTheDocument();
    expect(within(box).queryByLabelText("Setor")).not.toBeInTheDocument();
    expect(within(box).getByText("Bruno Costa")).toBeInTheDocument();
  });
});

describe("demand drawer: leaving", () => {
  it("closes with the button", async () => {
    const user = userEvent.setup({ delay: null });
    setup();

    const box = await drawer();
    await user.click(within(box).getByRole("button", { name: "Fechar detalhe" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("closes with Escape", async () => {
    const user = userEvent.setup({ delay: null });
    setup();
    await drawer();

    await user.keyboard("{Escape}");

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("moves focus into the drawer when it opens", async () => {
    setup();

    const box = await drawer();
    await waitFor(() => expect(box.contains(document.activeElement)).toBe(true));
  });
});
