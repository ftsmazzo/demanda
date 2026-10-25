import { describe, expect, it } from "vitest";
import { makeCard } from "../test/fixtures";
import { stuckCards, teamLoad } from "./panel";

const ana = { id: "u-1", name: "Ana Lima" };
const bruno = { id: "u-2", name: "Bruno Costa" };

describe("stuckCards", () => {
  it("lists only open demands, the most idle first, up to the limit", () => {
    const cards = [
      makeCard({ id: "a", idle_hours: 5 }),
      makeCard({ id: "b", idle_hours: 90, status: "aguardando" }),
      makeCard({ id: "c", idle_hours: 200, status: "concluido" }),
      makeCard({ id: "d", idle_hours: 30 }),
    ];

    expect(stuckCards(cards, 2).map((card) => card.id)).toEqual(["b", "d"]);
  });
});

describe("teamLoad", () => {
  it("counts open demands per person by status, busiest first, unassigned last", () => {
    const cards = [
      makeCard({ id: "a", assignee: ana, status: "novo" }),
      makeCard({ id: "b", assignee: bruno, status: "em_andamento" }),
      makeCard({ id: "c", assignee: bruno, status: "aguardando" }),
      makeCard({ id: "d", assignee: bruno, status: "concluido" }),
      makeCard({ id: "e", assignee: null, status: "novo" }),
      makeCard({ id: "f", assignee: null, status: "novo" }),
    ];

    const load = teamLoad(cards);

    expect(load.map((row) => [row.name, row.total])).toEqual([
      ["Bruno Costa", 2],
      ["Ana Lima", 1],
      ["Sem responsável", 2],
    ]);
    expect(load[0].byStatus).toEqual({ novo: 0, em_andamento: 1, aguardando: 1 });
  });

  it("is empty when nothing is open", () => {
    expect(teamLoad([makeCard({ status: "concluido" })])).toEqual([]);
  });
});
