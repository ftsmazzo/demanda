export type Status = "novo" | "em_andamento" | "aguardando" | "concluido";
export type Sector =
  | "triagem"
  | "fiscal"
  | "contabil"
  | "dp"
  | "societario"
  | "financeiro"
  | "rh-interno";
export type Urgency = "normal" | "alta" | "critica";
export type Kind = "tarefa" | "compromisso" | "duvida" | "documento" | "cobranca" | "reclamacao";
export type ContactKind = "cliente" | "fornecedor" | "colaborador" | "desconhecido";
export type Role = "socio" | "gestor" | "colaborador";

export interface PersonRef {
  id: string;
  name: string;
}

export interface ContactRef {
  id: string;
  name: string | null;
  phone: string;
  kind: ContactKind;
}

export interface Progress {
  done: number;
  total: number;
  percent: number;
}

export interface Card {
  id: string;
  title: string;
  sector: Sector;
  kind: string;
  urgency: Urgency;
  status: Status;
  due_date: string | null;
  origin: "auto" | "manual";
  assignee: PersonRef | null;
  contact: ContactRef | null;
  progress: Progress;
  messages_count: number;
  created_at: string;
  last_activity_at: string;
  closed_at: string | null;
  idle_hours: number;
  summary: string | null;
  next_step: string | null;
  needs_review: boolean;
  review_reason: string | null;
}

export interface Message {
  id: string;
  direction: "in" | "out";
  text: string | null;
  type: string;
  sent_at: string;
}

export interface Subtask {
  id: string;
  title: string;
  done: boolean;
}

export type EventKind =
  | "created"
  | "attached"
  | "summary"
  | "appointment_created"
  | "appointment_updated"
  | "proposal"
  | "merged"
  | "split"
  | "review";

export interface CaseEvent {
  id: string;
  actor: "ai" | "rules" | "user";
  kind: EventKind;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: Record<string, any>;
  created_at: string;
}

export interface AppointmentBrief {
  id: string;
  title: string;
  starts_at: string;
  all_day: boolean;
  status: "proposed" | "confirmed" | "cancelled";
}

export interface Detail extends Card {
  messages: Message[];
  subtasks: Subtask[];
  events: CaseEvent[];
  appointments: AppointmentBrief[];
}

export interface ConversationMessage extends Message {
  demand_id: string | null;
}

export interface Conversation {
  contact: ContactRef;
  cases: Card[];
  messages: ConversationMessage[];
}

export interface Column {
  status: Status;
  count: number;
  demands: Card[];
}

export interface Board {
  columns: Column[];
}

export interface Me {
  id: string;
  email: string;
  name: string;
  role: Role;
  sectors: Sector[];
}

export interface UserOut {
  id: string;
  name: string;
  role: Role;
  sectors: Sector[];
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface DemandPatch {
  title?: string;
  status?: Status;
  urgency?: Urgency;
  sector?: Sector;
  due_date?: string | null;
  assignee_id?: string | null;
  needs_review?: boolean;
}

export interface DemandCreate {
  title: string;
  sector: Sector;
  kind?: Kind;
  urgency?: Urgency;
  due_date?: string | null;
  assignee_id?: string | null;
  contact_id?: string | null;
}

export interface BoardFilters {
  sector?: Sector | "";
  assignee?: string;
}

export interface ChannelHealth {
  id: string;
  name: string;
  state: string | null;
  healthy: boolean;
  changed_at: string | null;
  checked_at: string | null;
}

export type AppointmentStatus = "proposed" | "confirmed" | "cancelled";

export interface Appointment {
  id: string;
  title: string;
  starts_at: string;
  all_day: boolean;
  status: AppointmentStatus;
  demand_id: string;
  sector: Sector;
  contact: ContactRef | null;
}
