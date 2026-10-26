export const KIND_LABEL: Record<string, string> = {
  tarefa: "Tarefa",
  compromisso: "Compromisso",
  duvida: "Dúvida",
  documento: "Documento",
  cobranca: "Cobrança",
  reclamacao: "Reclamação",
  nota: "Nota",
};

/** Tarefa e o caso comum do quadro: so os outros tipos ganham etiqueta. */
export const kindTag = (kind: string): string | null =>
  kind === "tarefa" ? null : (KIND_LABEL[kind] ?? null);
