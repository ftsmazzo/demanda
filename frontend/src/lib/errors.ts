import { ApiError } from "../api/client";

export const SAVE_FAILED = "Não foi possível salvar. Tente de novo.";

/** Texto de erro para quem esta usando a tela: o que houve e o que fazer. */
export function saveErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 403) return "Você não tem permissão para fazer essa alteração.";
    if (error.status === 404) return "Esta demanda não existe ou você não tem acesso a ela.";
    if (error.status === 422) return "Alguma informação não foi aceita. Confira e tente de novo.";
    if (error.status === 0) return error.detail;
  }
  return SAVE_FAILED;
}
