import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { AppRoutes } from "./App";
import { COLABORADOR, GESTOR, SOCIO, makeBoard } from "./test/fixtures";
import { renderApp, type Handlers } from "./test/utils";
import type { Me } from "./api/types";

function signedInAs(me: Me): Handlers {
  return {
    "GET /api/v1/me": () => [200, me],
    "GET /api/v1/board": () => [200, makeBoard([])],
    "GET /api/v1/users": () => [200, []],
    "GET /api/v1/contacts": () => [200, []],
  };
}

describe("app shell", () => {
  it("sends anonymous visitors to the login", async () => {
    renderApp(<AppRoutes />, { route: "/" });

    expect(await screen.findByRole("heading", { name: "Entrar" })).toBeInTheDocument();
  });

  it("shows every area to a socio", async () => {
    renderApp(<AppRoutes />, { signedIn: true, handlers: signedInAs(SOCIO) });

    expect(await screen.findByRole("link", { name: "Quadro" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Painel do sócio" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Contatos" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Carlos Mendes/ })).toBeInTheDocument();
  });

  it("hides the sócio panel from a gestor but keeps contacts", async () => {
    renderApp(<AppRoutes />, { signedIn: true, handlers: signedInAs(GESTOR) });

    expect(await screen.findByRole("link", { name: "Contatos" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Painel do sócio" })).not.toBeInTheDocument();
  });

  it("shows only the board to a colaborador", async () => {
    renderApp(<AppRoutes />, { signedIn: true, handlers: signedInAs(COLABORADOR) });

    expect(await screen.findByRole("link", { name: "Quadro" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Contatos" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Painel do sócio" })).not.toBeInTheDocument();
  });

  it("sends a colaborador away from areas that are not theirs", async () => {
    renderApp(<AppRoutes />, { route: "/painel", signedIn: true, handlers: signedInAs(COLABORADOR) });

    expect(await screen.findByRole("link", { name: "Hoje", current: "page" })).toBeInTheDocument();
  });

  it("falls back to today for unknown addresses", async () => {
    renderApp(<AppRoutes />, { route: "/nao-existe", signedIn: true, handlers: signedInAs(SOCIO) });

    expect(await screen.findByRole("link", { name: "Hoje", current: "page" })).toBeInTheDocument();
  });

  it("signs out from the user menu", async () => {
    const user = userEvent.setup({ delay: null });
    renderApp(<AppRoutes />, { signedIn: true, handlers: signedInAs(SOCIO) });

    await user.click(await screen.findByRole("button", { name: /Carlos Mendes/ }));
    await user.click(screen.getByRole("menuitem", { name: "Sair" }));

    expect(await screen.findByRole("heading", { name: "Entrar" })).toBeInTheDocument();
  });

  it("says it is loading while the profile arrives", () => {
    renderApp(<AppRoutes />, {
      signedIn: true,
      handlers: { "GET /api/v1/me": () => new Promise(() => {}) },
    });

    expect(screen.getByRole("status")).toHaveTextContent("Carregando");
  });
});
