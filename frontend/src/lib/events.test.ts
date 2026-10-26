import { describe, expect, it } from "vitest";
import type { CaseEvent } from "../api/types";
import { actorLabel, describeEvent } from "./events";

const event = (kind: string, data: Record<string, unknown> = {}, actor = "ai"): CaseEvent => ({
  id: kind,
  actor: actor as CaseEvent["actor"],
  kind: kind as CaseEvent["kind"],
  data,
  created_at: "2026-10-26T12:00:00Z",
});

describe("describeEvent", () => {
  it("says what happened in plain words", () => {
    expect(describeEvent(event("created"))).toBe("Caso aberto");
    expect(describeEvent(event("attached"))).toBe("Mensagem nova juntada e resumo atualizado");
    expect(describeEvent(event("merged", { from_title: "Outro caso" }))).toBe("Juntado a este caso: Outro caso");
    expect(describeEvent(event("review", { reason: "confirmar agrupamento" }))).toBe(
      "Marcado para revisão: confirmar agrupamento",
    );
  });

  it("writes appointment changes with the old and the new time", () => {
    const text = describeEvent(
      event("appointment_updated", {
        before: { starts_at: "2026-10-28T17:00:00Z", all_day: false },
        after: { starts_at: "2026-10-29T13:00:00Z", all_day: false },
      }),
    );

    expect(text).toBe("Compromisso remarcado de quarta-feira, 28/10 às 14:00 para quinta-feira, 29/10 às 10:00");
  });

  it("describes created appointments and unapplied proposals", () => {
    expect(describeEvent(event("appointment_created", { starts_at: "2026-10-28T17:00:00Z", all_day: false }))).toBe(
      "Compromisso criado para quarta-feira, 28/10 às 14:00",
    );
    expect(
      describeEvent(event("proposal", { proposed: { starts_at: "2026-10-29T13:00:00Z", all_day: false } })),
    ).toBe("Sugestão de remarcar para quinta-feira, 29/10 às 10:00 (não aplicada)");
  });

  it("does not break on unknown kinds or missing data", () => {
    expect(describeEvent(event("algo-novo"))).toBe("Caso atualizado");
    expect(describeEvent(event("appointment_updated"))).toBe("Compromisso remarcado");
  });
});

describe("actorLabel", () => {
  it("names who did it", () => {
    expect(actorLabel("ai")).toBe("IA");
    expect(actorLabel("rules")).toBe("Regras");
    expect(actorLabel("user")).toBe("Você");
  });
});
