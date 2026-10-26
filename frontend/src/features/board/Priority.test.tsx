import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { AppRoutes } from "../../App";
import { SOCIO, USERS, makeBoard, makeCard } from "../../test/fixtures";
import { renderApp } from "../../test/utils";

const vip = { id: "c-vip", name: "Mercado Bom Preço", phone: "5511999990109", kind: "cliente" as const, priority: true };

function open() {
  return renderApp(<AppRoutes />, {
    route: "/quadro",
    signedIn: true,
    handlers: {
      "GET /api/v1/me": () => [200, SOCIO],
      "GET /api/v1/board": () => [200, makeBoard([makeCard({ title: "Da prioritária", contact: vip }), makeCard({ title: "Da comum" })])],
      "GET /api/v1/users": () => [200, USERS],
    },
  });
}

describe("priority clients on the board", () => {
  it("tags the cards of priority clients", async () => {
    open();

    const card = (await screen.findByText("Da prioritária")).closest("button")!;
    const plain = screen.getByText("Da comum").closest("button")!;

    expect(within(card).getByText("Prioritário")).toBeInTheDocument();
    expect(within(plain).queryByText("Prioritário")).not.toBeInTheDocument();
  });

  it("filters to priority clients on the server", async () => {
    const { calls } = open();
    await screen.findByText("Da comum");

    await userEvent.click(screen.getByRole("button", { name: "Só prioritários" }));

    await waitFor(() => {
      const last = calls.filter((call) => call.key === "GET /api/v1/board").at(-1)!;
      expect(last.url.searchParams.get("priority")).toBe("true");
    });
    expect(screen.getByRole("button", { name: "Só prioritários" })).toHaveAttribute("aria-pressed", "true");
  });
});
