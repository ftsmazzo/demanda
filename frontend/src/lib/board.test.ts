import { describe, expect, it } from "vitest";
import { makeBoard, makeCard } from "../test/fixtures";
import { moveInBoard, sortCards } from "./board";

const NOW = "2026-10-25T12:00:00.000Z";

const laneOf = (board: ReturnType<typeof makeBoard>, status: string) =>
  board.columns.find((column) => column.status === status)!;

describe("moveInBoard", () => {
  it("moves a card to another lane and updates both counts", () => {
    const board = makeBoard([makeCard({ id: "a" }), makeCard({ id: "b" })]);

    const next = moveInBoard(board, "a", "em_andamento", NOW);

    expect(laneOf(next, "novo").demands.map((card) => card.id)).toEqual(["b"]);
    expect(laneOf(next, "novo").count).toBe(1);
    expect(laneOf(next, "em_andamento").demands.map((card) => card.id)).toEqual(["a"]);
    expect(laneOf(next, "em_andamento").count).toBe(1);
  });

  it("counts the move as activity", () => {
    const board = makeBoard([makeCard({ id: "a", idle_hours: 80 })]);

    const moved = laneOf(moveInBoard(board, "a", "aguardando", NOW), "aguardando").demands[0];

    expect(moved.status).toBe("aguardando");
    expect(moved.idle_hours).toBe(0);
    expect(moved.closed_at).toBeNull();
  });

  it("stamps the closing time when a demand is concluded", () => {
    const board = makeBoard([makeCard({ id: "a" })]);

    const moved = laneOf(moveInBoard(board, "a", "concluido", NOW), "concluido").demands[0];

    expect(moved.closed_at).toBe(NOW);
  });

  it("clears the closing time when a demand is reopened", () => {
    const board = makeBoard([makeCard({ id: "a", status: "concluido", closed_at: "2026-10-20T10:00:00Z" })]);

    const moved = laneOf(moveInBoard(board, "a", "novo", NOW), "novo").demands[0];

    expect(moved.closed_at).toBeNull();
  });

  it("keeps urgent demands on top of the target lane", () => {
    const board = makeBoard([
      makeCard({ id: "calm", status: "em_andamento", urgency: "normal", idle_hours: 90 }),
      makeCard({ id: "hot", urgency: "critica" }),
    ]);

    const lane = laneOf(moveInBoard(board, "hot", "em_andamento", NOW), "em_andamento");

    expect(lane.demands.map((card) => card.id)).toEqual(["hot", "calm"]);
  });

  it("does nothing for unknown cards or the same lane", () => {
    const board = makeBoard([makeCard({ id: "a" })]);

    expect(moveInBoard(board, "zzz", "novo", NOW)).toBe(board);
    expect(moveInBoard(board, "a", "novo", NOW)).toBe(board);
  });

  it("does not change the original board", () => {
    const board = makeBoard([makeCard({ id: "a" })]);

    moveInBoard(board, "a", "aguardando", NOW);

    expect(laneOf(board, "novo").demands).toHaveLength(1);
  });
});

describe("sortCards", () => {
  it("orders by urgency, then by time without movement", () => {
    const cards = [
      makeCard({ id: "old-normal", urgency: "normal", idle_hours: 90 }),
      makeCard({ id: "new-high", urgency: "alta", idle_hours: 1 }),
      makeCard({ id: "old-critical", urgency: "critica", idle_hours: 50 }),
      makeCard({ id: "new-normal", urgency: "normal", idle_hours: 2 }),
    ];

    expect(sortCards(cards).map((card) => card.id)).toEqual([
      "old-critical",
      "new-high",
      "old-normal",
      "new-normal",
    ]);
  });
});
