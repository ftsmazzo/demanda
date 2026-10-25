import type { Card, Status } from "../api/types";

export type OpenStatus = Exclude<Status, "concluido">;

export interface LoadRow {
  id: string | null;
  name: string;
  total: number;
  byStatus: Record<OpenStatus, number>;
}

const isOpen = (card: Card) => card.status !== "concluido";

export function stuckCards(cards: Card[], limit: number): Card[] {
  return cards
    .filter(isOpen)
    .sort((a, b) => b.idle_hours - a.idle_hours)
    .slice(0, limit);
}

export function teamLoad(cards: Card[]): LoadRow[] {
  const rows = new Map<string | null, LoadRow>();
  for (const card of cards.filter(isOpen)) {
    const id = card.assignee?.id ?? null;
    let row = rows.get(id);
    if (!row) {
      row = {
        id,
        name: card.assignee?.name ?? "Sem responsável",
        total: 0,
        byStatus: { novo: 0, em_andamento: 0, aguardando: 0 },
      };
      rows.set(id, row);
    }
    row.total += 1;
    row.byStatus[card.status as OpenStatus] += 1;
  }
  return [...rows.values()].sort((a, b) => {
    if ((a.id === null) !== (b.id === null)) return a.id === null ? 1 : -1;
    return b.total - a.total;
  });
}
