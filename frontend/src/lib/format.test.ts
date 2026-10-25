import { describe, expect, it } from "vitest";
import { makeCard } from "../test/fixtures";
import { ageFill, idleBadge, idleLevel, initials, spanText, voiceSentence } from "./format";

describe("idle time", () => {
  it.each([
    [0, 0],
    [23.9, 0],
    [24, 1],
    [71, 1],
    [72, 2],
    [200, 2],
  ])("level of %s hours is %i", (hours, level) => {
    expect(idleLevel(hours)).toBe(level);
  });

  it.each([
    [0.2, "1 h"],
    [5.7, "5 h"],
    [24, "1 dia"],
    [47, "1 dia"],
    [48, "2 dias"],
    [100, "4 dias"],
  ])("writes %s hours as %s", (hours, text) => {
    expect(spanText(hours)).toBe(text);
  });

  it("keeps the gauge visible when new and full when old", () => {
    expect(ageFill(0)).toBe(12);
    expect(ageFill(36)).toBe(56);
    expect(ageFill(72)).toBe(100);
    expect(ageFill(500)).toBe(100);
  });
});

describe("idle badge", () => {
  const now = Date.parse("2026-10-25T12:00:00Z");

  it("says how long an open demand has been still", () => {
    expect(idleBadge(makeCard({ idle_hours: 52 }), now)).toBe("há 2 dias");
    expect(idleBadge(makeCard({ idle_hours: 6 }), now)).toBe("há 6 h");
  });

  it("says a demand was just touched", () => {
    expect(idleBadge(makeCard({ idle_hours: 0 }), now)).toBe("agora");
  });

  it("says how long ago a demand was closed", () => {
    const closed = makeCard({ status: "concluido", closed_at: "2026-10-22T12:00:00Z", idle_hours: 0 });

    expect(idleBadge(closed, now)).toBe("Concluída há 3 dias");
  });

  it("copes with a closed demand without a date", () => {
    expect(idleBadge(makeCard({ status: "concluido", closed_at: null }), now)).toBe("Concluída");
  });
});

describe("voice sentence", () => {
  const stuck = (hours = 30) => makeCard({ idle_hours: hours });
  const critical = (hours = 5) => makeCard({ urgency: "critica", idle_hours: hours });

  it("combines critical and stuck demands", () => {
    expect(voiceSentence([critical(), stuck(), stuck(), stuck()])).toBe(
      "Hoje, 1 demanda crítica pede a sua atenção e 3 estão paradas há mais de um dia.",
    );
  });

  it("counts a critical demand that is also stuck in both groups", () => {
    expect(voiceSentence([critical(40), critical(2)])).toBe(
      "Hoje, 2 demandas críticas pedem a sua atenção e 1 está parada há mais de um dia.",
    );
  });

  it("speaks only about critical ones when nothing is stuck", () => {
    expect(voiceSentence([critical(), critical()])).toBe(
      "Hoje, 2 demandas críticas pedem a sua atenção.",
    );
  });

  it("speaks only about stuck ones when none is critical", () => {
    expect(voiceSentence([stuck(), stuck()])).toBe("2 demandas estão paradas há mais de um dia.");
    expect(voiceSentence([stuck()])).toBe("Uma demanda está parada há mais de um dia.");
  });

  it("ignores closed demands", () => {
    const done = makeCard({ status: "concluido", urgency: "critica", idle_hours: 90 });

    expect(voiceSentence([done])).toBe("Tudo em movimento hoje.");
  });

  it("is calm when the board is empty", () => {
    expect(voiceSentence([])).toBe("Tudo em movimento hoje.");
  });
});

describe("initials", () => {
  it("uses first and last name", () => {
    expect(initials("Carlos Mendes")).toBe("CM");
    expect(initials("  maria  da  silva ")).toBe("MS");
    expect(initials("Ana")).toBe("A");
    expect(initials("")).toBe("?");
  });
});
