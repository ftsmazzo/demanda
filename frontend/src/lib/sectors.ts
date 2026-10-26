import type { Sector, Status, Urgency } from "../api/types";

export const SECTOR_LABEL: Record<Sector, string> = {
  fiscal: "Fiscal",
  contabil: "Contábil",
  dp: "Pessoal",
  societario: "Societário",
  financeiro: "Financeiro",
  triagem: "Triagem",
  "rh-interno": "RH interno",
  consultoria: "Consultoria",
};

export const SECTOR_COLOR: Record<Sector, string> = {
  fiscal: "var(--sector-fiscal)",
  contabil: "var(--sector-contabil)",
  dp: "var(--sector-dp)",
  societario: "var(--sector-societario)",
  financeiro: "var(--sector-financeiro)",
  triagem: "var(--sector-triagem)",
  "rh-interno": "var(--sector-rh)",
  consultoria: "var(--sector-consultoria)",
};

export const SECTORS = Object.keys(SECTOR_LABEL) as Sector[];

export const STATUS_LABEL: Record<Status, string> = {
  novo: "Novas",
  em_andamento: "Em andamento",
  aguardando: "Aguardando",
  concluido: "Concluídas",
};

export const STATUS_SINGULAR: Record<Status, string> = {
  novo: "Nova",
  em_andamento: "Em andamento",
  aguardando: "Aguardando",
  concluido: "Concluída",
};

export const STATUSES = Object.keys(STATUS_LABEL) as Status[];

export const URGENCY_LABEL: Record<Urgency, string> = {
  normal: "Normal",
  alta: "Alta",
  critica: "Crítica",
};
