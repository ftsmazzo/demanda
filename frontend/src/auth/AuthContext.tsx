import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { createApi, type Api } from "../api/endpoints";
import { createClient } from "../api/client";
import type { Me } from "../api/types";
import { clearSession, loadSession, rememberTenant, saveSession, type Session } from "./session";

export const EXPIRED_NOTICE = "Sua sessão expirou. Entre de novo.";
const MAX_TIMER = 2 ** 31 - 1;

interface AuthValue {
  status: "anonymous" | "authenticated";
  api: Api;
  login: (tenant: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  notice: string | null;
}

const AuthContext = createContext<AuthValue | null>(null);

interface ProviderProps {
  children: ReactNode;
  fetchImpl?: typeof fetch;
}

export function AuthProvider({ children, fetchImpl }: ProviderProps) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState<Session | null>(() => loadSession());
  const [notice, setNotice] = useState<string | null>(null);
  const tokenRef = useRef<string | null>(session?.token ?? null);
  tokenRef.current = session?.token ?? null;

  const endSession = useCallback(
    (message: string | null) => {
      clearSession();
      setSession(null);
      setNotice(message);
      queryClient.clear();
    },
    [queryClient],
  );

  const api = useMemo(
    () =>
      createApi(
        createClient({
          getToken: () => tokenRef.current,
          onUnauthorized: () => endSession(EXPIRED_NOTICE),
          fetchImpl,
        }),
      ),
    [endSession, fetchImpl],
  );

  const login = useCallback(
    async (tenant: string, email: string, password: string) => {
      const response = await api.login(tenant, email, password);
      const next: Session = {
        token: response.access_token,
        expiresAt: Date.now() + response.expires_in * 1000,
      };
      saveSession(next);
      rememberTenant(tenant);
      setNotice(null);
      setSession(next);
    },
    [api],
  );

  const logout = useCallback(() => endSession(null), [endSession]);

  useEffect(() => {
    if (!session) return;
    const wait = Math.min(Math.max(session.expiresAt - Date.now(), 0), MAX_TIMER);
    const timer = window.setTimeout(() => endSession(EXPIRED_NOTICE), wait);
    return () => window.clearTimeout(timer);
  }, [session, endSession]);

  const value = useMemo<AuthValue>(
    () => ({ status: session ? "authenticated" : "anonymous", api, login, logout, notice }),
    [session, api, login, logout, notice],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth precisa estar dentro de AuthProvider");
  return value;
}

export function useMe() {
  const { api, status } = useAuth();
  return useQuery<Me>({
    queryKey: ["me"],
    queryFn: () => api.me(),
    enabled: status === "authenticated",
    staleTime: 5 * 60_000,
  });
}
