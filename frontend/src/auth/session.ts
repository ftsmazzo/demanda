const SESSION_KEY = "demanda.session";
const TENANT_KEY = "demanda.tenant";

export interface Session {
  token: string;
  expiresAt: number;
}

export function saveSession(session: Session): void {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  } catch {
    // armazenamento bloqueado: a sessao vale so enquanto a aba estiver aberta
  }
}

export function loadSession(): Session | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as Partial<Session>;
    if (typeof data.token !== "string" || typeof data.expiresAt !== "number") return null;
    if (data.expiresAt <= Date.now()) {
      clearSession();
      return null;
    }
    return { token: data.token, expiresAt: data.expiresAt };
  } catch {
    return null;
  }
}

export function clearSession(): void {
  try {
    sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // sem armazenamento, nada a limpar
  }
}

export function rememberTenant(slug: string): void {
  try {
    localStorage.setItem(TENANT_KEY, slug);
  } catch {
    // preferencia opcional
  }
}

export function rememberedTenant(): string {
  try {
    return localStorage.getItem(TENANT_KEY) ?? "";
  } catch {
    return "";
  }
}
