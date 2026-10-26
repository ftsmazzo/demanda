import type { Appointment } from "../api/types";

export type CalendarView = "week" | "month" | "list";

const pad = (value: number) => String(value).padStart(2, "0");

export const dayKey = (date: Date) => date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate());

export function addDays(date: Date, days: number): Date {
  const next = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  next.setDate(next.getDate() + days);
  return next;
}

export function startOfWeek(date: Date): Date {
  const offset = (date.getDay() + 6) % 7; // segunda = 0
  return addDays(date, -offset);
}

export const weekDays = (date: Date): Date[] => Array.from({ length: 7 }, (_, i) => addDays(startOfWeek(date), i));

export function monthGrid(date: Date): Date[] {
  const first = new Date(date.getFullYear(), date.getMonth(), 1);
  const last = new Date(date.getFullYear(), date.getMonth() + 1, 0);
  const start = startOfWeek(first);
  const end = addDays(startOfWeek(last), 6);
  const total = Math.round((end.getTime() - start.getTime()) / 86_400_000) + 1;
  return Array.from({ length: total }, (_, i) => addDays(start, i));
}

const monthName = (date: Date) => date.toLocaleDateString("pt-BR", { month: "long" });

export function rangeLabel(view: CalendarView, date: Date): string {
  if (view === "month") return monthName(date) + " de " + date.getFullYear();
  const days = weekDays(date);
  const first = days[0];
  const last = days[6];
  if (first.getMonth() === last.getMonth()) {
    return first.getDate() + " a " + last.getDate() + " de " + monthName(last) + " de " + last.getFullYear();
  }
  return first.getDate() + " de " + monthName(first) + " a " + last.getDate() + " de " + monthName(last) + " de " + last.getFullYear();
}

export interface Placed {
  item: Appointment;
  top: number; // % da altura visivel
  height: number; // % da altura visivel
  lane: number;
  lanes: number;
}

const DURATION_MINUTES = 60;

/** Posicao vertical de cada compromisso no dia (horas visiveis de `from` a `to`) e colunas lado a lado. */
export function layoutDay(items: Appointment[], from: number, to: number): Placed[] {
  const span = (to - from) * 60;
  const sorted = [...items].sort((a, b) => a.starts_at.localeCompare(b.starts_at));
  const placed = sorted.map((item) => {
    const start = new Date(item.starts_at);
    const minutes = Math.min(Math.max(start.getHours() * 60 + start.getMinutes() - from * 60, 0), span - 20);
    const top = (minutes / span) * 100;
    const height = Math.min((DURATION_MINUTES / span) * 100, 100 - top);
    return { item, top, height, lane: 0, lanes: 1, end: minutes + DURATION_MINUTES, begin: minutes };
  });
  let group: typeof placed = [];
  let groupEnd = -1;
  const flush = () => {
    const lanes = group.reduce((max, entry) => Math.max(max, entry.lane + 1), 1);
    for (const entry of group) entry.lanes = lanes;
    group = [];
  };
  for (const entry of placed) {
    if (group.length && entry.begin >= groupEnd) flush();
    const taken = new Set(group.filter((other) => other.end > entry.begin).map((other) => other.lane));
    while (taken.has(entry.lane)) entry.lane += 1;
    group.push(entry);
    groupEnd = Math.max(groupEnd, entry.end);
  }
  flush();
  return placed.map(({ item, top, height, lane, lanes }) => ({ item, top, height, lane, lanes }));
}
