import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { makeBoard, makeCard } from "../test/fixtures";
import { renderApp, type Handlers } from "../test/utils";
import { useMoveDemand } from "./move";
import { useBoard } from "./queries";

function Probe() {
  const board = useBoard({});
  const move = useMoveDemand();
  const count = (status: string) => board.data?.columns.find((c) => c.status === status)?.demands.length ?? "?";
  return (
    <div>
      <p>novo: {count("novo")}</p>
      <p>aguardando: {count("aguardando")}</p>
      <p>erro: {move.error ? "sim" : "nao"}</p>
      <button onClick={() => move.mutate({ id: "a", to: "aguardando" })}>mover</button>
    </div>
  );
}

const board = () => makeBoard([makeCard({ id: "a" })]);

function setup(patch: Handlers[string]) {
  return renderApp(<Probe />, {
    signedIn: true,
    handlers: { "GET /api/v1/board": () => [200, board()], "PATCH /api/v1/demands/a": patch },
  });
}

describe("useMoveDemand", () => {
  it("moves the card right away, before the server answers", async () => {
    const user = userEvent.setup({ delay: null });
    let answer: (value: [number, unknown]) => void = () => {};
    setup(() => new Promise((resolve) => (answer = resolve)));
    await screen.findByText("novo: 1");

    await user.click(screen.getByRole("button", { name: "mover" }));

    expect(await screen.findByText("novo: 0")).toBeInTheDocument();
    expect(screen.getByText("aguardando: 1")).toBeInTheDocument();
    answer([200, {}]);
  });

  it("sends only the new status", async () => {
    const user = userEvent.setup({ delay: null });
    const { calls } = setup(() => [200, {}]);
    await screen.findByText("novo: 1");

    await user.click(screen.getByRole("button", { name: "mover" }));

    await waitFor(() => expect(calls.some((c) => c.key === "PATCH /api/v1/demands/a")).toBe(true));
    expect(calls.find((c) => c.key === "PATCH /api/v1/demands/a")!.body).toEqual({ status: "aguardando" });
  });

  it("puts the card back when the server refuses", async () => {
    const user = userEvent.setup({ delay: null });
    setup(() => [403, { detail: "sem permissao" }]);
    await screen.findByText("novo: 1");

    await user.click(screen.getByRole("button", { name: "mover" }));

    await waitFor(() => expect(screen.getByText("erro: sim")).toBeInTheDocument());
    expect(screen.getByText("novo: 1")).toBeInTheDocument();
    expect(screen.getByText("aguardando: 0")).toBeInTheDocument();
  });
});
