import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { renderApp } from "../test/utils";
import { SOCIO } from "../test/fixtures";
import { useAuth, useMe } from "./AuthContext";
import { loadSession } from "./session";

function Probe() {
  const auth = useAuth();
  const me = useMe();
  return (
    <div>
      <p>estado: {auth.status}</p>
      <p>notice: {auth.notice ?? "nenhum"}</p>
      <p>usuario: {me.data?.name ?? "sem usuario"}</p>
      <button onClick={() => auth.logout()}>sair</button>
      <button onClick={() => void auth.api.board().catch(() => {})}>carregar</button>
    </div>
  );
}

describe("AuthProvider", () => {
  it("starts anonymous without a saved session", () => {
    renderApp(<Probe />);

    expect(screen.getByText("estado: anonymous")).toBeInTheDocument();
  });

  it("starts authenticated with a saved session and loads the user", async () => {
    renderApp(<Probe />, { signedIn: true, handlers: { "GET /api/v1/me": () => [200, SOCIO] } });

    expect(screen.getByText("estado: authenticated")).toBeInTheDocument();
    expect(await screen.findByText("usuario: Carlos Mendes")).toBeInTheDocument();
  });

  it("logout clears the stored session", async () => {
    const user = userEvent.setup({ delay: null });
    renderApp(<Probe />, { signedIn: true, handlers: { "GET /api/v1/me": () => [200, SOCIO] } });

    await user.click(screen.getByRole("button", { name: "sair" }));

    expect(screen.getByText("estado: anonymous")).toBeInTheDocument();
    expect(loadSession()).toBeNull();
  });

  it("ends the session with a notice when the server says it expired", async () => {
    const user = userEvent.setup({ delay: null });
    renderApp(<Probe />, {
      signedIn: true,
      handlers: {
        "GET /api/v1/me": () => [200, SOCIO],
        "GET /api/v1/board": () => [401, { detail: "nao autenticado" }],
      },
    });
    await screen.findByText("usuario: Carlos Mendes");

    await user.click(screen.getByRole("button", { name: "carregar" }));

    await waitFor(() => expect(screen.getByText("estado: anonymous")).toBeInTheDocument());
    expect(screen.getByText("notice: Sua sessão expirou. Entre de novo.")).toBeInTheDocument();
    expect(loadSession()).toBeNull();
  });
});
