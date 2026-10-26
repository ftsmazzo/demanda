"""Alteracoes pedidas pelo socio: viram uma proposta e so o "1" executa (vale 15 minutos)."""

from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from app.core.demands import lift_for_priority

PENDING_TTL = timedelta(minutes=15)
_STATUS_LABEL = {
    "novo": "nova",
    "em_andamento": "em andamento",
    "aguardando": "aguardando",
    "concluido": "concluída",
}


def propose(
    conn: psycopg.Connection,
    tenant_id: UUID,
    recipient_id: UUID,
    kind: str,
    payload: dict[str, Any],
    summary: str,
    now: datetime,
) -> None:
    """Guarda a proposta e cancela a anterior: so a mais recente espera resposta."""
    conn.execute(
        "UPDATE agent_pending_actions SET status = 'superseded', resolved_at = %s "
        "WHERE recipient_id = %s AND status = 'pending'",
        (now, recipient_id),
    )
    conn.execute(
        "INSERT INTO agent_pending_actions (tenant_id, recipient_id, kind, payload, summary, "
        "created_at, expires_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (tenant_id, recipient_id, kind, Jsonb(payload), summary, now, now + PENDING_TTL),
    )


def _event(conn, tenant_id, demand_id, kind, data) -> None:
    conn.execute(
        "INSERT INTO case_events (tenant_id, demand_id, actor, kind, data) "
        "VALUES (%s, %s, 'user', %s, %s)",
        (tenant_id, demand_id, kind, Jsonb(data)),
    )


def _create_task(conn, tenant_id, p: dict[str, Any], app_url: str) -> str:
    contact_id = UUID(p["contact_id"]) if p.get("contact_id") else None
    urgency = lift_for_priority(conn, contact_id, p.get("urgency") or "normal")
    demand_id = conn.execute(
        "INSERT INTO demands (tenant_id, contact_id, sector, kind, urgency, title, assignee_id, "
        "due_date, origin) VALUES (%s, %s, %s, 'tarefa', %s, %s, %s, %s, 'manual') RETURNING id",
        (
            tenant_id,
            contact_id,
            p["sector"],
            urgency,
            p["title"],
            UUID(p["assignee_id"]) if p.get("assignee_id") else None,
            date.fromisoformat(p["due_date"]) if p.get("due_date") else None,
        ),
    ).fetchone()[0]
    _event(conn, tenant_id, demand_id, "created", {"title": p["title"], "via": "agente"})
    who = f" para {p['assignee_name']}" if p.get("assignee_name") else ""
    return f"Pronto: tarefa criada{who}.\nQuadro: {app_url.rstrip('/')}/"


def _open_demand(conn, demand_id: str):
    return conn.execute(
        "SELECT id, title FROM demands WHERE id = %s AND status <> 'concluido' FOR UPDATE",
        (UUID(demand_id),),
    ).fetchone()


def _assign(conn, tenant_id, p: dict[str, Any], app_url: str) -> str:
    found = _open_demand(conn, p["demand_id"])
    person = conn.execute(
        "SELECT name FROM users WHERE id = %s AND active", (UUID(p["assignee_id"]),)
    ).fetchone()
    if found is None or person is None:
        return "Não consegui: a demanda ou a pessoa não está mais disponível."
    conn.execute(
        "UPDATE demands SET assignee_id = %s, updated_at = now() WHERE id = %s",
        (UUID(p["assignee_id"]), found[0]),
    )
    _event(conn, tenant_id, found[0], "assigned", {"to": person[0], "via": "agente"})
    return f"Pronto: {found[1]} agora é de {person[0]}."


def _set_status(conn, tenant_id, p: dict[str, Any], app_url: str) -> str:
    found = _open_demand(conn, p["demand_id"])
    if found is None:
        return "Não consegui: a demanda não está mais aberta."
    closed = (
        "closed_at = COALESCE(closed_at, now())"
        if p["status"] == "concluido"
        else "closed_at = NULL"
    )
    conn.execute(
        f"UPDATE demands SET status = %s, {closed}, last_activity_at = now(), updated_at = now() "
        "WHERE id = %s",
        (p["status"], found[0]),
    )
    _event(conn, tenant_id, found[0], "status_changed", {"to": p["status"], "via": "agente"})
    return f"Pronto: {found[1]} agora está {_STATUS_LABEL[p['status']]}."


def _mark_priority(conn, tenant_id, p: dict[str, Any], app_url: str) -> str:
    done = conn.execute(
        "UPDATE contacts SET priority = %s, updated_at = now() WHERE id = %s RETURNING name",
        (p["value"], UUID(p["contact_id"])),
    ).fetchone()
    if done is None:
        return "Não consegui: o cliente não está mais disponível."
    state = "prioritário" if p["value"] else "comum de novo"
    return f"Pronto: {done[0]} agora é cliente {state}."


def _reschedule(conn, tenant_id, p: dict[str, Any], app_url: str) -> str:
    found = conn.execute(
        "SELECT id, demand_id, title, starts_at, all_day FROM appointments "
        "WHERE id = %s AND status <> 'cancelled' FOR UPDATE",
        (UUID(p["appointment_id"]),),
    ).fetchone()
    if found is None:
        return "Não consegui: o compromisso não está mais disponível."
    appointment_id, demand_id, title, starts_at, all_day = found
    starts = datetime.fromisoformat(p["starts_at"])
    conn.execute(
        "UPDATE appointments SET starts_at = %s, all_day = %s, updated_at = now() WHERE id = %s",
        (starts, p["all_day"], appointment_id),
    )
    conn.execute(
        "UPDATE demands SET last_activity_at = now(), updated_at = now() WHERE id = %s",
        (demand_id,),
    )
    data = {
        "appointment_id": str(appointment_id),
        "before": {"starts_at": starts_at.isoformat(), "all_day": all_day},
        "after": {"starts_at": starts.isoformat(), "all_day": p["all_day"]},
        "via": "agente",
    }
    _event(conn, tenant_id, demand_id, "appointment_updated", data)
    return f"Pronto: {title} remarcado para {p['when_label']}."


_EXECUTORS = {
    "reschedule": _reschedule,
    "create_task": _create_task,
    "assign": _assign,
    "set_status": _set_status,
    "mark_priority": _mark_priority,
}


def resolve_pending(
    conn: psycopg.Connection,
    tenant_id: UUID,
    recipient_id: UUID,
    command: str,
    now: datetime,
    app_url: str,
) -> str | None:
    """Trata o 1 (executa) ou o 2 (cancela) da proposta em aberto. None: nao ha proposta valida."""
    conn.execute(
        "UPDATE agent_pending_actions SET status = 'expired', resolved_at = %s "
        "WHERE recipient_id = %s AND status = 'pending' AND expires_at <= %s",
        (now, recipient_id, now),
    )
    row = conn.execute(
        "SELECT id, kind, payload, summary FROM agent_pending_actions "
        "WHERE recipient_id = %s AND status = 'pending' ORDER BY created_at DESC LIMIT 1 "
        "FOR UPDATE",
        (recipient_id,),
    ).fetchone()
    if row is None:
        return None
    action_id, kind, payload, summary = row
    if command == "cancel":
        conn.execute(
            "UPDATE agent_pending_actions SET status = 'cancelled', resolved_at = %s WHERE id = %s",
            (now, action_id),
        )
        return f"Cancelado: {summary}"
    reply = _EXECUTORS[kind](conn, tenant_id, payload, app_url)
    conn.execute(
        "UPDATE agent_pending_actions SET status = 'done', resolved_at = %s WHERE id = %s",
        (now, action_id),
    )
    return reply
