import { describe, expect, it } from "vitest";
import type { Appointment } from "../api/types";
import { addDays, dayKey, layoutDay, monthGrid, rangeLabel, startOfWeek, weekDays } from "./calendar";

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

describe("week and month", () => {
  it("starts the week on Monday", () => {
    expect(dayKey(startOfWeek(new Date(2026, 9, 25)))).toBe("2026-10-19"); // domingo
    expect(dayKey(startOfWeek(new Date(2026, 9, 26)))).toBe("2026-10-26"); // segunda
    expect(dayKey(startOfWeek(new Date(2026, 9, 28)))).toBe("2026-10-26");
  });

  it("lists the seven days of a week and moves across months", () => {
    const days = weekDays(new Date(2026, 9, 28)).map(dayKey);

    expect(days).toEqual(["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31", "2026-11-01"]);
    expect(dayKey(addDays(new Date(2026, 9, 31), 1))).toBe("2026-11-01");
  });

  it("builds a month grid of whole weeks that includes the neighbouring days", () => {
    const grid = monthGrid(new Date(2026, 9, 15));

    expect(grid.length % 7).toBe(0);
    expect(dayKey(grid[0])).toBe("2026-09-28");
    expect(grid.map(dayKey)).toContain("2026-10-31");
    expect(dayKey(grid[grid.length - 1])).toBe("2026-11-01");
  });

  it("names the visible range", () => {
    expect(rangeLabel("week", new Date(2026, 9, 28))).toBe("26 de outubro a 1 de novembro de 2026");
    expect(rangeLabel("week", new Date(2026, 9, 14))).toBe("12 a 18 de outubro de 2026");
    expect(rangeLabel("month", new Date(2026, 9, 14))).toBe("outubro de 2026");
  });
});

describe("layoutDay", () => {
  it("places an event by its time inside the visible hours", () => {
    const [placed] = layoutDay([item("a", "2026-10-28T17:00:00Z")], 7, 20); // 14:00 local

    expect(placed.top).toBeCloseTo((7 / 13) * 100, 1);
    expect(placed.height).toBeGreaterThan(5);
  });

  it("clamps events outside the visible hours", () => {
    const [early, late] = layoutDay([item("e", "2026-10-28T08:00:00Z"), item("l", "2026-10-29T01:00:00Z")], 7, 20);

    expect(early.top).toBe(0);
    expect(late.top + late.height).toBeLessThanOrEqual(100.0001);
  });

  it("puts overlapping events side by side", () => {
    const placed = layoutDay(
      [item("a", "2026-10-28T17:00:00Z"), item("b", "2026-10-28T17:30:00Z"), item("c", "2026-10-28T21:00:00Z")],
      7,
      20,
    );

    expect(placed.map((p) => [p.item.id, p.lane, p.lanes])).toEqual([
      ["a", 0, 2],
      ["b", 1, 2],
      ["c", 0, 1],
    ]);
  });
});
