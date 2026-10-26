import type { CaseEvent } from "../api/types";
import { whenLabel } from "./agenda";

const ACTORS: Record<CaseEvent["actor"], string> = { ai: "IA", rules: "Regras", user: "Você" };

export const actorLabel = (actor: CaseEvent["actor"]): string => ACTORS[actor] ?? "Sistema";

interface When {
  starts_at?: string;
  all_day?: boolean;
}

const label = (when: When | undefined): string | null =>
  when?.starts_at ? whenLabel(when.starts_at, Boolean(when.all_day)) : null;

/** Uma frase simples para cada passo do historico do caso. */
export function describeEvent(event: CaseEvent): string {
  const { data } = event;
  switch (event.kind) {
    case "created":
      return "Caso aberto";
    case "attached":
      return "Mensagem nova juntada e resumo atualizado";
    case "merged":
      return data.from_title ? `Juntado a este caso: ${data.from_title}` : "Casos juntados";
    case "review":
      return data.reason ? `Marcado para revisão: ${data.reason}` : "Marcado para revisão";
    case "appointment_created": {
      const when = label(data);
      return when ? `Compromisso criado para ${when}` : "Compromisso criado";
    }
    case "appointment_updated": {
      const before = label(data.before);
      const after = label(data.after);
      return before && after ? `Compromisso remarcado de ${before} para ${after}` : "Compromisso remarcado";
    }
    case "proposal": {
      const when = label(data.proposed);
      return when ? `Sugestão de remarcar para ${when} (não aplicada)` : "Sugestão de remarcação (não aplicada)";
    }
    default:
      return "Caso atualizado";
  }
}
