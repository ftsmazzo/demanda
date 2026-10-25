import { describe, expect, it } from "vitest";
import type { Appointment } from "../api/types";
import { dayLabel, groupByDay, timeLabel } from "./agenda";

const NOW = new Date("2026-10-25T15:00:00Z"); // domingo 12:00 em Sao Paulo

const item = (id: string, startsAt: string, allDay = false): Appointment => ({
  id,
  title: id,
  starts_at: startsAt,
  all_day: allDay,
  status: "proposed",
  demand_id: "d",
  sector: "fiscal",
  contact: null,
});

describe("timeLabel", () => {
  it("shows the clock time, or says it lasts the whole day", () => {
    expect(timeLabel(item("a", "2026-10-28T17:00:00Z"))).toBe("14:00");
    expect(timeLabel(item("b", "2026-10-28T03:00:00Z", true))).toBe("O dia todo");
  });
});

describe("dayLabel", () => {
  it("names today and tomorrow, then the weekday and date", () => {
    expect(dayLabel(new Date("2026-10-25T20:00:00Z"), NOW)).toBe("Hoje");
    expect(dayLabel(new Date("2026-10-26T13:00:00Z"), NOW)).toBe("Amanhã");
    expect(dayLabel(new Date("2026-10-28T17:00:00Z"), NOW)).toBe("quarta-feira, 28 de outubro");
  });
});

describe("groupByDay", () => {
  it("groups by local day keeping the order", () => {
    const groups = groupByDay(
      [
        item("a", "2026-10-28T17:00:00Z"),
        item("b", "2026-10-28T19:00:00Z"),
        item("c", "2026-10-29T12:00:00Z"),
      ],
      NOW,
    );

    expect(groups.map((group) => [group.label, group.items.map((i) => i.id)])).toEqual([
      ["quarta-feira, 28 de outubro", ["a", "b"]],
      ["quinta-feira, 29 de outubro", ["c"]],
    ]);
  });

  it("keeps a late-evening appointment on its local day, not the UTC one", () => {
    const [group] = groupByDay([item("noite", "2026-10-29T01:30:00Z")], NOW); // 28/10 22:30 local

    expect(group.label).toBe("quarta-feira, 28 de outubro");
  });
});
