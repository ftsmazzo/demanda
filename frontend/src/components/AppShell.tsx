import { useEffect, useRef, useState } from "react";
import { NavLink, Navigate, Outlet, useOutletContext, useSearchParams } from "react-router-dom";
import { useAuth, useMe } from "../auth/AuthContext";
import type { Me, Role } from "../api/types";
import { DemandDrawer } from "../features/demand/DemandDrawer";
import { initials } from "../lib/format";
import { ChannelAlert } from "./ChannelAlert";
import { Icon, type IconName } from "./Icon";
import { Mark } from "./Mark";

interface NavItem {
  to: string;
  label: string;
  icon: IconName;
  roles: Role[];
}

const NAV: NavItem[] = [
  { to: "/", label: "Quadro", icon: "board", roles: ["socio", "gestor", "colaborador"] },
  { to: "/painel", label: "Painel do sócio", icon: "chart", roles: ["socio"] },
  { to: "/contatos", label: "Contatos", icon: "people", roles: ["socio", "gestor"] },
];

function UserMenu({ me }: { me: Me }) {
  const { logout } = useAuth();
  const [open, setOpen] = useState(false);
  const holder = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent && event.key !== "Escape") return;
      if (event instanceof MouseEvent && holder.current?.contains(event.target as Node)) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  return (
    <div className="user-menu" ref={holder}>
      <button
        type="button"
        className="me"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`${me.name}, menu da conta`}
        onClick={() => setOpen((value) => !value)}
      >
        {initials(me.name)}
      </button>
      {open ? (
        <div className="menu" role="menu" aria-label="Conta">
          <p className="menu-name">{me.name}</p>
          <button type="button" role="menuitem" className="menu-item" onClick={logout}>
            Sair
          </button>
        </div>
      ) : null}
    </div>
  );
}

function DemandDrawerHost({ me }: { me: Me }) {
  const [params, setParams] = useSearchParams();
  const id = params.get("demanda");
  if (!id) return null;
  const close = () => {
    const next = new URLSearchParams(params);
    next.delete("demanda");
    setParams(next);
  };
  return <DemandDrawer key={id} id={id} me={me} onClose={close} />;
}

export function AppShell() {
  const me = useMe();

  if (me.isPending) {
    return (
      <p role="status" className="loading">
        Carregando…
      </p>
    );
  }
  if (!me.data) {
    return (
      <div className="loading" role="alert">
        <p>Não foi possível carregar seus dados.</p>
        <button className="btn" type="button" onClick={() => void me.refetch()}>
          Tentar de novo
        </button>
      </div>
    );
  }

  const user = me.data;
  return (
    <div className="app">
      <nav className="rail" aria-label="Principal">
        <span className="mark">
          <Mark />
        </span>
        {NAV.filter((item) => item.roles.includes(user.role)).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className="rail-link"
            title={item.label}
            aria-label={item.label}
          >
            <Icon name={item.icon} />
          </NavLink>
        ))}
        <span className="rail-spacer" />
        <UserMenu me={user} />
      </nav>
      <main className="main">
        <ChannelAlert me={user} />
        <Outlet context={user} />
      </main>
      <DemandDrawerHost me={user} />
    </div>
  );
}

export function useCurrentUser(): Me {
  return useOutletContext<Me>();
}

export function RequireAuth() {
  const { status } = useAuth();
  return status === "authenticated" ? <Outlet /> : <Navigate to="/login" replace />;
}

export function RequireRole({ roles, children }: { roles: Role[]; children: React.ReactNode }) {
  const user = useCurrentUser();
  return roles.includes(user.role) ? <>{children}</> : <Navigate to="/" replace />;
}
