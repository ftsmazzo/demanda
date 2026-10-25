import { waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { SOCIO } from "../../test/fixtures";
import { detail, drawer, setup } from "./testkit";

describe("demand drawer: reading", () => {
  it("shows the demand, its contact and how long it has been still", async () => {
    setup();

    const box = await drawer();
    expect(within(box).getByRole("heading", { name: "Já pedi 3 vezes a certidão negativa" })).toBeInTheDocument();
    expect(within(box).getByText(/Padaria Pão Quente/)).toBeInTheDocument();
    expect(within(box).getByText(/Parada há 1 dia/)).toBeInTheDocument();
    expect(box.querySelector(".drawer-top .sector")).toHaveTextContent("Societário");
  });

  it("shows the conversation with each side apart", async () => {
    setup();

    const box = await drawer();
    expect(within(box).getByText("Boa tarde, preciso da guia.")).toBeInTheDocument();
    expect(within(box).getByText("Já estamos vendo.").closest(".msg")).toHaveClass("out");
    expect(within(box).getByText("Boa tarde, preciso da guia.").closest(".msg")).not.toHaveClass("out");
  });

  it("explains a demand that is gone or off limits", async () => {
    setup(SOCIO, detail(), { "GET /api/v1/demands/d1": () => [404, { detail: "demanda nao encontrada" }] });

    const box = await drawer();
    expect(await within(box).findByText("Esta demanda não existe ou você não tem acesso a ela.")).toBeInTheDocument();
  });
});

describe("demand drawer: steps", () => {
  it("shows the progress of the steps", async () => {
    setup();

    const box = await drawer();
    expect(within(box).getByText("1 de 2")).toBeInTheDocument();
    expect(within(box).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "50");
    expect(within(box).getByRole("checkbox", { name: "Emitir a certidão" })).toBeChecked();
    expect(within(box).getByRole("checkbox", { name: "Localizar o pedido anterior" })).not.toBeChecked();
  });

  it("ticks a step and saves it", async () => {
    const user = userEvent.setup({ delay: null });
    let saved = false;
    const ticked = detail({
      subtasks: [
        { id: "s1", title: "Localizar o pedido anterior", done: true },
        { id: "s2", title: "Emitir a certidão", done: true },
      ],
      progress: { done: 2, total: 2, percent: 100 },
    });
    const { calls } = setup(SOCIO, detail(), {
      "PATCH /api/v1/subtasks/s1": () => {
        saved = true;
        return [200, { id: "s1", title: "Localizar o pedido anterior", done: true }];
      },
      // o servidor de verdade devolve o estado salvo quando a tela recarrega
      "GET /api/v1/demands/d1": () => [200, saved ? ticked : detail()],
    });

    const box = await drawer();
    await user.click(within(box).getByRole("checkbox", { name: "Localizar o pedido anterior" }));

    expect(within(box).getByRole("checkbox", { name: "Localizar o pedido anterior" })).toBeChecked();
    expect(within(box).getByText("2 de 2")).toBeInTheDocument();
    await waitFor(() => expect(calls.some((c) => c.key === "PATCH /api/v1/subtasks/s1")).toBe(true));
    expect(calls.find((c) => c.key === "PATCH /api/v1/subtasks/s1")!.body).toEqual({ done: true });
  });

  it("undoes a tick that could not be saved and says so", async () => {
    const user = userEvent.setup({ delay: null });
    setup(SOCIO, detail(), { "PATCH /api/v1/subtasks/s1": () => [500, { detail: "x" }] });

    const box = await drawer();
    await user.click(within(box).getByRole("checkbox", { name: "Localizar o pedido anterior" }));

    expect(await within(box).findByRole("alert")).toHaveTextContent("Não foi possível salvar. Tente de novo.");
    expect(within(box).getByRole("checkbox", { name: "Localizar o pedido anterior" })).not.toBeChecked();
  });

  it("adds a step", async () => {
    const user = userEvent.setup({ delay: null });
    const { calls } = setup(SOCIO, detail(), {
      "POST /api/v1/demands/d1/subtasks": ({ body }) => [201, { id: "s3", title: body.title, done: false }],
    });

    const box = await drawer();
    await user.type(within(box).getByLabelText("Nova etapa"), "Responder ao cliente{enter}");

    expect(await within(box).findByRole("checkbox", { name: "Responder ao cliente" })).toBeInTheDocument();
    expect(calls.find((c) => c.key === "POST /api/v1/demands/d1/subtasks")!.body).toEqual({ title: "Responder ao cliente" });
    expect(within(box).getByLabelText("Nova etapa")).toHaveValue("");
  });
});
