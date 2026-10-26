import type { Board, Card, Detail, Me, Status, UserOut } from "../api/types";

let counter = 0;

export function makeCard(overrides: Partial<Card> = {}): Card {
  counter += 1;
  return {
    id: `d-${counter}`,
    title: `Demanda ${counter}`,
    sector: "fiscal",
    kind: "tarefa",
    urgency: "normal",
    status: "novo",
    due_date: null,
    origin: "auto",
    assignee: null,
    contact: { id: "c-1", name: "Padaria Pão Quente", phone: "5511999990101", kind: "cliente", priority: false },
    progress: { done: 0, total: 0, percent: 0 },
    messages_count: 1,
    created_at: "2026-10-20T12:00:00Z",
    last_activity_at: "2026-10-20T12:00:00Z",
    closed_at: null,
    idle_hours: 2,
    summary: null,
    next_step: null,
    needs_review: false,
    review_reason: null,
    ...overrides,
  };
}

export function makeDetail(overrides: Partial<Detail> = {}): Detail {
  return {
    ...makeCard(),
    messages: [
      { id: "m-1", direction: "in", text: "Boa tarde, preciso da guia.", type: "conversation", sent_at: "2026-10-20T12:00:00Z" },
      { id: "m-2", direction: "out", text: "Já estamos vendo.", type: "conversation", sent_at: "2026-10-20T12:30:00Z" },
    ],
    subtasks: [],
    events: [],
    appointments: [],
    ...overrides,
  };
}

const STATUSES: Status[] = ["novo", "em_andamento", "aguardando", "concluido"];

export function makeBoard(cards: Card[] = []): Board {
  return {
    columns: STATUSES.map((status) => {
      const demands = cards.filter((card) => card.status === status);
      return { status, count: demands.length, demands };
    }),
  };
}

export const SOCIO: Me = {
  id: "u-1",
  email: "carlos@exemplo.com",
  name: "Carlos Mendes",
  role: "socio",
  sectors: [],
};

export const GESTOR: Me = { ...SOCIO, id: "u-2", name: "Rafael Souza", role: "gestor", sectors: ["fiscal"] };
export const COLABORADOR: Me = { ...SOCIO, id: "u-3", name: "Bruno Costa", role: "colaborador", sectors: ["fiscal"] };

export const USERS: UserOut[] = [
  { id: "u-1", name: "Carlos Mendes", role: "socio", sectors: [] },
  { id: "u-2", name: "Rafael Souza", role: "gestor", sectors: ["fiscal"] },
  { id: "u-3", name: "Bruno Costa", role: "colaborador", sectors: ["fiscal"] },
];
