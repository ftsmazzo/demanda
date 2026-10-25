import type { Card } from "../api/types";

export type IdleLevel = 0 | 1 | 2;

export function idleLevel(hours: number): IdleLevel {
  if (hours >= 72) return 2;
  if (hours >= 24) return 1;
  return 0;
}

export function spanText(hours: number): string {
  if (hours >= 48) return `${Math.floor(hours / 24)} dias`;
  if (hours >= 24) return "1 dia";
  return `${Math.max(1, Math.floor(hours))} h`;
}

/** Quanto do medidor de envelhecimento fica cheio: de 12% (recente) a 100% (72 h parada). */
export function ageFill(hours: number): number {
  return Math.min(100, Math.max(12, 12 + (hours / 72) * 88));
}

type IdleSource = Pick<Card, "status" | "idle_hours" | "closed_at">;

export function idleBadge(card: IdleSource, now: number = Date.now()): string {
  if (card.status === "concluido") {
    if (!card.closed_at) return "Concluída";
    const hours = (now - Date.parse(card.closed_at)) / 3_600_000;
    return `Concluída há ${spanText(Math.max(hours, 0))}`;
  }
  if (card.idle_hours < 1) return "agora";
  return `há ${spanText(card.idle_hours)}`;
}

export function voiceSentence(cards: Pick<Card, "status" | "urgency" | "idle_hours">[]): string {
  const open = cards.filter((card) => card.status !== "concluido");
  const critical = open.filter((card) => card.urgency === "critica").length;
  const stuck = open.filter((card) => card.idle_hours >= 24).length;

  const criticalText = critical === 1 ? "1 demanda crítica pede" : `${critical} demandas críticas pedem`;
  const stuckText = stuck === 1 ? "1 está parada" : `${stuck} estão paradas`;

  if (critical && stuck) return `Hoje, ${criticalText} a sua atenção e ${stuckText} há mais de um dia.`;
  if (critical) return `Hoje, ${criticalText} a sua atenção.`;
  if (stuck === 1) return "Uma demanda está parada há mais de um dia.";
  if (stuck) return `${stuck} demandas estão paradas há mais de um dia.`;
  return "Tudo em movimento hoje.";
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (parts[0][0] + last).toUpperCase();
}
