"""Entende o pedido do socio em linguagem natural e responde (consulta) ou propoe (alteracao)."""

import logging
from datetime import date, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg

from app.agent.messages import _day, unknown_text
from app.agent.nl import actions, queries
from app.agent.nl.contract import Intent
from app.agent.nl.llm import IntentContext, IntentLLM
from app.agent.nl.lookup import find_appointments, find_contacts, find_demands, find_users
from app.agent.runner import SECTOR_LABEL
from app.core.appointments import _tenant_zone
from app.core.schedule import extract_when
from app.db import Database

logger = logging.getLogger(__name__)

MIN_CONFIDENCE = 0.5
DEFAULT_DAILY_CAP = 100
MAX_TEAM = 30
_STATUS_LABEL = {
    "novo": "nova",
    "em_andamento": "em andamento",
    "aguardando": "aguardando",
    "concluido": "concluída",
}


def _reserve(conn: psycopg.Connection, tenant_id: UUID, day: date, cap: int) -> bool:
    if cap <= 0:
        return False
    row = conn.execute(
        "INSERT INTO ai_usage (tenant_id, day, purpose, calls) VALUES (%s, %s, 'agent', 1) "
        "ON CONFLICT (tenant_id, day, purpose) DO UPDATE SET calls = ai_usage.calls + 1 "
        "WHERE ai_usage.calls < %s RETURNING calls",
        (tenant_id, day, cap),
    ).fetchone()
    return row is not None


def _options(label: str, options: list[tuple[Any, str]]) -> str:
    names = "\n".join(f"- {name}" for _, name in options[:5])
    return f"Encontrei mais de um {label}:\n{names}\nRepita o pedido com mais detalhe."


def _ask(summary: str) -> str:
    return f"Vou {summary}.\nResponda 1 para confirmar ou 2 para cancelar."


def _person(conn, name: str | None):
    """(id, nome) da pessoa citada, (None, None) se nao citou, ou uma resposta de erro (str)."""
    if not name:
        return None, None
    found = find_users(conn, name)
    if not found:
        return f"Não encontrei ninguém chamado {name}."
    if len(found) > 1:
        return _options("nome", found)
    return found[0]


def _propose_task(conn, tenant_id, recipient_id, intent: Intent, local_now, now) -> str:
    person = _person(conn, intent.assignee_name)
    if isinstance(person, str):
        return person
    assignee_id, assignee_name = person
    contact_id, contact_name, note = None, None, ""
    if intent.contact_name:
        clients = find_contacts(conn, intent.contact_name)
        if len(clients) > 1:
            return _options("cliente", clients)
        if clients:
            contact_id, contact_name = clients[0]
        else:
            note = f" (não achei o cliente {intent.contact_name}: fica sem cliente)"
    sector = intent.sector
    if sector is None and assignee_id is not None:
        owned = conn.execute(
            "SELECT sector FROM user_sectors WHERE user_id = %s", (assignee_id,)
        ).fetchall()
        sector = owned[0][0] if len(owned) == 1 else None
    sector = sector or "triagem"
    due = extract_when(intent.due_phrase, local_now) if intent.due_phrase else None
    parts = [f"criar a tarefa *{intent.title}*"]
    parts.append(f"para {assignee_name}" if assignee_name else "sem responsável")
    if contact_name:
        parts.append(f"do cliente {contact_name}")
    parts.append(f"({SECTOR_LABEL.get(sector, sector)})")
    if due:
        parts.append(f"com prazo {_day(due.start.date())}")
    summary = " ".join(parts) + note
    payload = {
        "title": intent.title,
        "sector": sector,
        "urgency": intent.urgency,
        "assignee_id": str(assignee_id) if assignee_id else None,
        "assignee_name": assignee_name,
        "contact_id": str(contact_id) if contact_id else None,
        "due_date": due.start.date().isoformat() if due else None,
    }
    actions.propose(conn, tenant_id, recipient_id, "create_task", payload, summary, now)
    return _ask(summary)


def _pick_demand(conn, intent: Intent):
    found = find_demands(conn, intent.case_text or "", open_only=True)
    if not found:
        return f"Não achei nenhuma demanda aberta com: {intent.case_text}."
    if len(found) > 1:
        return _options("caso", found)
    return found[0]


def _propose_assign(conn, tenant_id, recipient_id, intent: Intent, now) -> str:
    target = _pick_demand(conn, intent)
    if isinstance(target, str):
        return target
    person = _person(conn, intent.assignee_name)
    if isinstance(person, str):
        return person
    summary = f"passar *{target[1]}* para {person[1]}"
    payload = {"demand_id": str(target[0]), "assignee_id": str(person[0])}
    actions.propose(conn, tenant_id, recipient_id, "assign", payload, summary, now)
    return _ask(summary)


def _propose_status(conn, tenant_id, recipient_id, intent: Intent, now) -> str:
    target = _pick_demand(conn, intent)
    if isinstance(target, str):
        return target
    summary = f"marcar *{target[1]}* como {_STATUS_LABEL[intent.status]}"
    payload = {"demand_id": str(target[0]), "status": intent.status}
    actions.propose(conn, tenant_id, recipient_id, "set_status", payload, summary, now)
    return _ask(summary)


def _draft_text(first_name: str, title: str, summary: str | None, next_step: str | None) -> str:
    lines = [f"Oi, {first_name}! Pode cuidar disto? {title}."]
    if summary:
        lines.append(summary)
    if next_step:
        lines.append(f"Próximo passo: {next_step}")
    lines.append("Obrigado!")
    return "\n".join(lines)


def _propose_draft(conn, tenant_id, recipient_id, intent: Intent, now) -> str:
    target = _pick_demand(conn, intent)
    if isinstance(target, str):
        return target
    person = _person(conn, intent.assignee_name)
    if isinstance(person, str):
        return person
    title, summary, next_step = conn.execute(
        "SELECT title, summary, next_step FROM demands WHERE id = %s", (target[0],)
    ).fetchone()
    first_name = person[1].split()[0]
    text = _draft_text(first_name, title, summary, next_step)
    summary = f"entregar o rascunho para {first_name} (sobre {title})"
    payload = {"first_name": first_name, "text": text}
    actions.propose(conn, tenant_id, recipient_id, "draft_message", payload, summary, now)
    return f"Rascunho para {first_name}:\n\n{text}\n\nResponda 1 para aprovar ou 2 para cancelar."


def _propose_priority(conn, tenant_id, recipient_id, intent: Intent, now) -> str:
    clients = find_contacts(conn, intent.contact_name or "")
    if not clients:
        return f"Não encontrei nenhum cliente chamado {intent.contact_name}."
    if len(clients) > 1:
        return _options("cliente", clients)
    client_id, name = clients[0]
    summary = (
        f"marcar {name} como cliente prioritário"
        if intent.priority_value
        else f"tirar a prioridade de {name}"
    )
    payload = {"contact_id": str(client_id), "value": intent.priority_value}
    actions.propose(conn, tenant_id, recipient_id, "mark_priority", payload, summary, now)
    return _ask(summary)


def _when_label(start: datetime, all_day: bool) -> str:
    return f"{_day(start.date())}" + ("" if all_day else f" às {start:%H:%M}")


def _propose_reschedule(conn, tenant_id, recipient_id, intent: Intent, zone, now) -> str:
    found = find_appointments(conn, intent.case_text or "", now)
    if not found:
        return f"Não achei nenhum compromisso marcado com: {intent.case_text}."
    if len(found) > 1:
        return _options("compromisso", found)
    when = extract_when(intent.due_phrase or "", now.astimezone(zone))
    if when is None:
        return "Não entendi o dia e a hora novos. Repita o pedido, por exemplo: quinta às 15h."
    appointment_id, title = found[0]
    old = conn.execute(
        "SELECT starts_at, all_day FROM appointments WHERE id = %s", (appointment_id,)
    ).fetchone()
    label = _when_label(when.start.astimezone(zone), when.all_day)
    summary = f"remarcar *{title}* de {_when_label(old[0].astimezone(zone), old[1])} para {label}"
    payload = {
        "appointment_id": str(appointment_id),
        "starts_at": when.start.isoformat(),
        "all_day": when.all_day,
        "when_label": label,
    }
    actions.propose(conn, tenant_id, recipient_id, "reschedule", payload, summary, now)
    return _ask(summary)


def _dispatch(conn, tenant_id, recipient_id, intent: Intent, zone, now, app_url) -> str:
    local_now = now.astimezone(zone)
    if intent.intent == "query_demands":
        return queries.query_demands(conn, intent, now, app_url)
    if intent.intent == "query_agenda":
        return queries.query_agenda(conn, intent, zone, now)
    if intent.intent == "summary":
        return queries.summary(conn, zone, now, app_url)
    if intent.intent == "create_task":
        return _propose_task(conn, tenant_id, recipient_id, intent, local_now, now)
    if intent.intent == "assign":
        return _propose_assign(conn, tenant_id, recipient_id, intent, now)
    if intent.intent == "set_status":
        return _propose_status(conn, tenant_id, recipient_id, intent, now)
    if intent.intent == "mark_priority":
        return _propose_priority(conn, tenant_id, recipient_id, intent, now)
    if intent.intent == "draft_message":
        return _propose_draft(conn, tenant_id, recipient_id, intent, now)
    if intent.intent == "reschedule":
        return _propose_reschedule(conn, tenant_id, recipient_id, intent, zone, now)
    return unknown_text()


def natural_reply(
    db: Database,
    tenant_id: UUID,
    recipient_id: UUID,
    llm: IntentLLM,
    text: str,
    app_url: str,
    now: datetime,
    daily_cap: int = DEFAULT_DAILY_CAP,
) -> str:
    with db.tenant_transaction(tenant_id) as conn:
        zone: ZoneInfo = _tenant_zone(conn, tenant_id)
        if not _reserve(conn, tenant_id, datetime.now(zone).date(), daily_cap):
            return unknown_text()
        team = tuple(
            row[0] for row in conn.execute("SELECT name FROM users WHERE active ORDER BY name")
        )[:MAX_TEAM]
    try:
        intent = llm.understand(text, IntentContext(now.astimezone(zone), team))
    except Exception as exc:
        logger.warning("IA do agente falhou (%s)", type(exc).__name__)
        return unknown_text()
    if intent.intent == "unknown" or intent.confidence < MIN_CONFIDENCE:
        return unknown_text()
    with db.tenant_transaction(tenant_id) as conn:
        return _dispatch(conn, tenant_id, recipient_id, intent, zone, now, app_url)
