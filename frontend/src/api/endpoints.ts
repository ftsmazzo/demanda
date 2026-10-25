import type { Client } from "./client";
import type {
  Board,
  BoardFilters,
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

export function createApi(client: Client) {
  const { request } = client;
  return {
    login: (tenant: string, email: string, password: string) =>
      request<LoginResponse>("POST", "/api/v1/auth/login", { tenant, email, password }, { auth: false }),
    me: () => request<Me>("GET", "/api/v1/me"),
    board: (filters: BoardFilters = {}) =>
      request<Board>("GET", "/api/v1/board", undefined, {
        query: { sector: filters.sector, assignee: filters.assignee },
      }),
    demand: (id: string) => request<Detail>("GET", `/api/v1/demands/${id}`),
    patchDemand: (id: string, patch: DemandPatch) =>
      request<Detail>("PATCH", `/api/v1/demands/${id}`, patch),
    createDemand: (body: DemandCreate) => request<Detail>("POST", "/api/v1/demands", body),
    addSubtask: (demandId: string, title: string) =>
      request<Subtask>("POST", `/api/v1/demands/${demandId}/subtasks`, { title }),
    patchSubtask: (id: string, patch: { title?: string; done?: boolean }) =>
      request<Subtask>("PATCH", `/api/v1/subtasks/${id}`, patch),
    users: () => request<UserOut[]>("GET", "/api/v1/users"),
    contacts: (query: { q?: string; kind?: ContactKind | "" } = {}) =>
      request<ContactRef[]>("GET", "/api/v1/contacts", undefined, { query: { ...query, limit: 100 } }),
    patchContact: (id: string, patch: { name?: string; kind?: ContactKind }) =>
      request<ContactRef>("PATCH", `/api/v1/contacts/${id}`, patch),
  };
}

export type Api = ReturnType<typeof createApi>;
