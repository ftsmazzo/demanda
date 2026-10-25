import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { loadSession, rememberTenant } from "../../auth/session";
import { renderApp, type Handlers } from "../../test/utils";
import { Login } from "./Login";

function renderLogin(handlers: Handlers = {}) {
  return renderApp(
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<p>Quadro aberto</p>} />
    </Routes>,
    { route: "/login", handlers },
  );
}

async function fill(user: ReturnType<typeof userEvent.setup>, tenant: string, email: string, password: string) {
  const tenantField = screen.getByLabelText("Empresa");
  await user.clear(tenantField);
  if (tenant) await user.type(tenantField, tenant);
  if (email) await user.type(screen.getByLabelText("E-mail"), email);
  if (password) await user.type(screen.getByLabelText("Senha"), password);
}

describe("Login", () => {
  it("opens with the remembered company", () => {
    rememberTenant("contabilidade-piloto");

    renderLogin();

    expect(screen.getByLabelText("Empresa")).toHaveValue("contabilidade-piloto");
  });

  it("signs in, stores the session and opens the board", async () => {
    const user = userEvent.setup({ delay: null });
    const { calls } = renderLogin({
      "POST /api/v1/auth/login": () => [200, { access_token: "tok-1", token_type: "bearer", expires_in: 3600 }],
    });

    await fill(user, "contabilidade-piloto", "carlos@exemplo.com", "senha-longa-123");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByText("Quadro aberto")).toBeInTheDocument();
    expect(calls[0].body).toEqual({
      tenant: "contabilidade-piloto",
      email: "carlos@exemplo.com",
      password: "senha-longa-123",
    });
    expect(loadSession()?.token).toBe("tok-1");
  });

  it("explains wrong credentials without saying which field is wrong", async () => {
    const user = userEvent.setup({ delay: null });
    renderLogin({ "POST /api/v1/auth/login": () => [401, { detail: "credenciais invalidas" }] });

    await fill(user, "contabilidade-piloto", "carlos@exemplo.com", "errada-errada");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("E-mail ou senha incorretos.");
    expect(loadSession()).toBeNull();
  });

  it.each([
    [429, "Muitas tentativas. Tente de novo em alguns minutos."],
    [503, "O sistema está ocupado. Tente de novo em instantes."],
    [500, "Não foi possível entrar agora. Tente de novo."],
  ])("explains a %i answer", async (status, message) => {
    const user = userEvent.setup({ delay: null });
    renderLogin({ "POST /api/v1/auth/login": () => [status, { detail: "x" }] });

    await fill(user, "contabilidade-piloto", "carlos@exemplo.com", "senha-longa-123");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(message);
  });

  it("asks for the missing fields without calling the server", async () => {
    const user = userEvent.setup({ delay: null });
    const { calls } = renderLogin();

    await fill(user, "contabilidade-piloto", "", "");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Preencha empresa, e-mail e senha.");
    expect(calls).toHaveLength(0);
  });

  it("blocks double submits while waiting", async () => {
    const user = userEvent.setup({ delay: null });
    let release: (value: [number, unknown]) => void = () => {};
    const { calls } = renderLogin({
      "POST /api/v1/auth/login": () => new Promise((resolve) => (release = resolve)),
    });

    await fill(user, "contabilidade-piloto", "carlos@exemplo.com", "senha-longa-123");
    await user.click(screen.getByRole("button", { name: "Entrar" }));

    const busy = await screen.findByRole("button", { name: "Entrando…" });
    expect(busy).toBeDisabled();
    await user.click(busy);
    expect(calls).toHaveLength(1);
    release([200, { access_token: "t", token_type: "bearer", expires_in: 60 }]);
    await waitFor(() => expect(screen.getByText("Quadro aberto")).toBeInTheDocument());
  });
});
