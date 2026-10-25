import { screen, waitFor, within } from "@testing-library/react";
import { AppRoutes } from "../../App";
import type { Detail, Me } from "../../api/types";
import { SOCIO, USERS, makeBoard, makeDetail } from "../../test/fixtures";
import { renderApp, type Handlers } from "../../test/utils";

export const detail = (overrides: Partial<Detail> = {}): Detail =>
  makeDetail({
    id: "d1",
    title: "Já pedi 3 vezes a certidão negativa",
    sector: "societario",
    urgency: "critica",
    idle_hours: 26,
    assignee: { id: "u-3", name: "Bruno Costa" },
    subtasks: [
      { id: "s1", title: "Localizar o pedido anterior", done: false },
      { id: "s2", title: "Emitir a certidão", done: true },
    ],
    progress: { done: 1, total: 2, percent: 50 },
    ...overrides,
  });

export function setup(me: Me = SOCIO, current: Detail = detail(), extra: Handlers = {}) {
  const handlers: Handlers = {
    "GET /api/v1/me": () => [200, me],
    "GET /api/v1/board": () => [200, makeBoard([current])],
    "GET /api/v1/users": () => [200, USERS],
    "GET /api/v1/demands/d1": () => [200, current],
    ...extra,
  };
  return renderApp(<AppRoutes />, { route: "/?demanda=d1", signedIn: true, handlers });
}

/** Abre a gaveta e espera o carregamento terminar. */
export async function drawer() {
  const box = await screen.findByRole("dialog");
  await waitFor(() =>
    expect(within(box).queryByText("Carregando a demanda…")).not.toBeInTheDocument(),
  );
  return box;
}
