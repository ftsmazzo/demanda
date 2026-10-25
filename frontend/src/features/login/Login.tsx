import { useState, type CSSProperties, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { rememberedTenant } from "../../auth/session";
import { Mark } from "../../components/Mark";

const BAR_HEIGHTS = [34, 62, 24, 80, 46, 92, 30, 70, 54, 100, 38, 66, 28, 84, 48, 58];
const BAR_COLORS = ["var(--age-0)", "var(--age-1)", "var(--age-2)"];

function messageFor(error: unknown): string {
  if (!(error instanceof ApiError)) return "Não foi possível entrar agora. Tente de novo.";
  if (error.status === 401) return "E-mail ou senha incorretos.";
  if (error.status === 429) return "Muitas tentativas. Tente de novo em alguns minutos.";
  if (error.status === 503) return "O sistema está ocupado. Tente de novo em instantes.";
  if (error.status === 0) return error.detail;
  return "Não foi possível entrar agora. Tente de novo.";
}

function Bars() {
  return (
    <div className="bars">
      {BAR_HEIGHTS.map((height, index) => (
        <i
          key={index}
          style={
            {
              "--h": `${height}%`,
              "--c": BAR_COLORS[height > 75 ? 2 : height > 45 ? 1 : 0],
              "--n": index,
            } as CSSProperties
          }
        />
      ))}
    </div>
  );
}

export function Login() {
  const { login, status, notice } = useAuth();
  const [tenant, setTenant] = useState(rememberedTenant);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (status === "authenticated") return <Navigate to="/" replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (!tenant.trim() || !email.trim() || !password) {
      setError("Preencha empresa, e-mail e senha.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await login(tenant.trim(), email.trim(), password);
    } catch (failure) {
      setError(messageFor(failure));
      setBusy(false);
    }
  }

  return (
    <main className="login">
      <section className="login-art" aria-hidden="true">
        <div className="word">
          <Mark size={30} onDark />
          Demanda
        </div>
        <p>Nada que chega ao escritório fica sem dono.</p>
        <Bars />
      </section>
      <section className="login-form">
        <form onSubmit={submit} noValidate>
          <h1>Entrar</h1>
          {notice ? (
            <p role="status" className="notice">
              {notice}
            </p>
          ) : null}
          <label className="field">
            Empresa
            <input
              className="input"
              name="tenant"
              autoComplete="organization"
              value={tenant}
              onChange={(e) => setTenant(e.target.value)}
            />
          </label>
          <label className="field">
            E-mail
            <input
              className="input"
              type="email"
              name="email"
              autoComplete="username"
              placeholder="voce@empresa.com.br"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label className="field">
            Senha
            <input
              className="input"
              type="password"
              name="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {error ? (
            <p role="alert" className="form-error">
              {error}
            </p>
          ) : null}
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? "Entrando…" : "Entrar"}
          </button>
          <p className="hint">Esqueceu a senha? Peça a um sócio para criar outra.</p>
        </form>
      </section>
    </main>
  );
}
