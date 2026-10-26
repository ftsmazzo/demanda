import type { Appointment } from "../../api/types";
import { addDays, monthGrid, startOfWeek, type CalendarView } from "../../lib/calendar";

export const LIST_DAYS = 30;

export function parseDate(value: string | null): Date {
  const match = value ? /^(\d{4})-(\d{2})-(\d{2})$/.exec(value) : null;
  if (!match) return new Date();
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

export function visibleRange(view: CalendarView, cursor: Date): { since: Date; until: Date } {
  if (view === "week") {
    const since = startOfWeek(cursor);
    return { since, until: addDays(since, 7) };
  }
  if (view === "month") {
    const grid = monthGrid(cursor);
    return { since: grid[0], until: addDays(grid[grid.length - 1], 1) };
  }
  const now = new Date();
  const since = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return { since, until: addDays(since, LIST_DAYS) };
}

export function voice(items: Appointment[]): string {
  const proposed = items.filter((item) => item.status === "proposed").length;
  if (proposed) {
    const noun = proposed === 1 ? "compromisso espera" : "compromissos esperam";
    return proposed + " " + noun + " a sua confirmação.";
  }
  return items.length ? "Tudo confirmado por aqui." : "Nenhum compromisso à vista.";
}
