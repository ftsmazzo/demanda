import type { Board, Card, Status } from "../api/types";

const URGENCY_RANK = { critica: 3, alta: 2, normal: 1 } as const;

/** Mesma ordem que o servidor usa: urgencia primeiro, depois o que esta parado ha mais tempo. */
export function sortCards(cards: Card[]): Card[] {
  return [...cards].sort(
    (a, b) =>
      URGENCY_RANK[b.urgency] - URGENCY_RANK[a.urgency] ||
      b.idle_hours - a.idle_hours ||
      Date.parse(b.last_activity_at) - Date.parse(a.last_activity_at),
  );
}

/** Quadro como ficaria depois de mover o card (atualizacao otimista, sem mexer no original). */
export function moveInBoard(board: Board, id: string, to: Status, nowIso: string): Board {
  const source = board.columns.find((column) => column.demands.some((card) => card.id === id));
  const card = source?.demands.find((item) => item.id === id);
  if (!source || !card || card.status === to) return board;

  const moved: Card = {
    ...card,
    status: to,
    idle_hours: 0,
    last_activity_at: nowIso,
    closed_at: to === "concluido" ? nowIso : null,
  };
  return {
    columns: board.columns.map((column) => {
      if (column.status === source.status) {
        return { ...column, count: column.count - 1, demands: column.demands.filter((item) => item.id !== id) };
      }
      if (column.status === to) {
        return { ...column, count: column.count + 1, demands: sortCards([...column.demands, moved]) };
      }
      return column;
    }),
  };
}
