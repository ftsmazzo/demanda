import type { Client } from "./client";
import type {
  Board,
  Appointment,
  AppointmentStatus,
  BoardFilters,
  ChannelHealth,
  Conversation,
  ConversationSummary,
  TodayData,
  ContactKind,
  ContactRef,
  DemandCreate,
  DemandPatch,
  Detail,
  LoginResponse,
  Me,
  Subtask,
  UserOut,
} from "./types";

const SAFE_ID = /^[A-Za-z0-9-]{1,64}$/;

/** Ids vem da URL da pagina: so entram no caminho se forem simples (sem "..", "/" ou "?"). */
function safeId(id: string): string {
  if (!SAFE_ID.test(id)) throw new Error("identificador invalido");
  return id;
}

export function createApi(client: Client) {
  const { request } = client;
  return {
    login: (tenant: string, email: string, password: string) =>
      request<LoginResponse>("POST", "/api/v1/auth/login", { tenant, email, password }, { auth: false }),
    me: () => request<Me>("GET", "/api/v1/me"),
    board: (filters: BoardFilters = {}) =>
      request<Board>("GET", "/api/v1/board", undefined, {
        query: {
          sector: filters.sector,
          assignee: filters.assignee,
          priority: filters.priority ? "true" : undefined,
        },
      }),
    demand: (id: string) => request<Detail>("GET", `/api/v1/demands/${safeId(id)}`),
    patchDemand: (id: string, patch: DemandPatch) =>
      request<Detail>("PATCH", `/api/v1/demands/${safeId(id)}`, patch),
    createDemand: (body: DemandCreate) => request<Detail>("POST", "/api/v1/demands", body),
    addSubtask: (demandId: string, title: string) =>
      request<Subtask>("POST", `/api/v1/demands/${safeId(demandId)}/subtasks`, { title }),
    patchSubtask: (id: string, patch: { title?: string; done?: boolean }) =>
      request<Subtask>("PATCH", `/api/v1/subtasks/${safeId(id)}`, patch),
    channelsHealth: () => request<ChannelHealth[]>("GET", "/api/v1/channels/health"),
    appointments: (range: { since?: string; until?: string; status?: AppointmentStatus } = {}) =>
      request<Appointment[]>("GET", "/api/v1/appointments", undefined, {
        query: { since: range.since, until: range.until, status: range.status, limit: 200 },
      }),
    today: () => request<TodayData>("GET", "/api/v1/today"),
    conversations: (filters: { q?: string; waiting?: boolean } = {}) =>
      request<ConversationSummary[]>("GET", "/api/v1/conversations", undefined, {
        query: { q: filters.q, waiting: filters.waiting ? "true" : undefined },
      }),
    patchAppointment: (
      id: string,
      patch: { status?: AppointmentStatus; starts_at?: string; all_day?: boolean },
    ) =>
      request<Appointment>("PATCH", `/api/v1/appointments/${safeId(id)}`, patch),
    mergeDemand: (id: string, into: string) =>
      request<Detail>("POST", `/api/v1/demands/${safeId(id)}/merge`, { into }),
    conversation: (contactId: string) =>
      request<Conversation>("GET", `/api/v1/contacts/${safeId(contactId)}/conversation`),
    users: () => request<UserOut[]>("GET", "/api/v1/users"),
    contacts: (query: { q?: string; kind?: ContactKind | "" } = {}) =>
      request<ContactRef[]>("GET", "/api/v1/contacts", undefined, { query: { ...query, limit: 100 } }),
    patchContact: (id: string, patch: { name?: string; kind?: ContactKind; priority?: boolean }) =>
      request<ContactRef>("PATCH", `/api/v1/contacts/${safeId(id)}`, patch),
  };
}

export type Api = ReturnType<typeof createApi>;
