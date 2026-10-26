"""O que o agente faz quando um socio escreve para ele: confirmar, cancelar, listar, ajudar."""

import logging
from datetime import datetime, time, timedelta
from uuid import UUID

import psycopg

from app.agent.commands import parse_command
from app.agent.messages import (
    agenda_text,
    already_text,
    cancelled_text,
    confirmed_text,
    help_text,
    nothing_stuck_text,
    nothing_to_confirm_text,
    stuck_text,
    unknown_text,
    when_text,
)
from app.agent.nl import actions as nl_actions
from app.agent.nl.llm import IntentLLM
from app.agent.nl.service import DEFAULT_DAILY_CAP, natural_reply
from app.agent.runner import stuck_items
from app.agent.sender import MessageSender, SendError
from app.core.appointments import _tenant_zone
from app.db import Database

logger = logging.getLogger(__name__)

REPLY_CAP = 60  # respostas por pessoa em 24 h: protege de laco e de abuso
STUCK_MINIMUM_HOURS = 24

_ALERTED = """
    SELECT a.id, a.title, a.starts_at, a.all_day, a.status
    FROM agent_notifications n JOIN appointments a ON a.id::text = n.dedupe_key
    WHERE n.recipient_id = %s AND n.kind = 'appointment' AND n.status IN ('sent', 'dry_run')
      {extra}
    ORDER BY n.created_at DESC, n.id DESC LIMIT 1
    FOR UPDATE OF a
"""


def _answer_appointment(conn, command: str, recipient_id, zone, app_url: str) -> str:
    row = conn.execute(
        _ALERTED.format(extra="AND a.status = 'proposed'"), (recipient_id,)
    ).fetchone()
    if row is None:
        row = conn.execute(_ALERTED.format(extra=""), (recipient_id,)).fetchone()
        if row is None:
            return nothing_to_confirm_text(app_url)
        return already_text(row[1], row[4])
    appointment_id, title, starts_at, all_day, _ = row
    new_status = "confirmed" if command == "confirm" else "cancelled"
    conn.execute(
        "UPDATE appointments SET status = %s, updated_at = now() WHERE id = %s",
        (new_status, appointment_id),
    )
    when = when_text(starts_at.astimezone(zone), all_day)
    return confirmed_text(title, when) if command == "confirm" else cancelled_text(title, when)


def _agenda(conn: psycopg.Connection, zone, app_url: str, now: datetime) -> str:
    local = now.astimezone(zone)
    start = datetime.combine(local.date(), time.min, tzinfo=zone)
    rows = conn.execute(
        "SELECT title, starts_at, all_day FROM appointments WHERE status <> 'cancelled' "
        "AND starts_at >= %s AND starts_at < %s ORDER BY starts_at, id",
        (start, start + timedelta(days=2)),
    ).fetchall()
    today, tomorrow = [], []
    for title, starts_at, all_day in rows:
        at = starts_at.astimezone(zone)
        entry = ("dia todo" if all_day else at.strftime("%H:%M"), title)
        (today if at.date() == local.date() else tomorrow).append(entry)
    return agenda_text(today, tomorrow, app_url)


def _respond(conn, tenant_id, command: str, recipient_id, zone, app_url: str, now: datetime) -> str:
    if command in ("confirm", "cancel"):
        pending = nl_actions.resolve_pending(conn, tenant_id, recipient_id, command, now, app_url)
        if pending is not None:
            return pending
        return _answer_appointment(conn, command, recipient_id, zone, app_url)
    if command == "stuck":
        items = stuck_items(conn, now, STUCK_MINIMUM_HOURS, 5)
        return stuck_text(items, app_url) if items else nothing_stuck_text()
    if command == "agenda":
        return _agenda(conn, zone, app_url, now)
    if command == "help":
        return help_text(app_url)
    return unknown_text()


def _send_reply(
    db: Database, tenant_id: UUID, sender: MessageSender, notification_id, phone, body, now
) -> None:
    try:
        sender.send(phone, body)
    except SendError as exc:
        status, sent_at, error = "failed", None, str(exc)[:200]
        logger.error("resposta %s nao enviada: %s", notification_id, exc)
    else:
        status, sent_at, error = sender.mode, now, None
    with db.tenant_transaction(tenant_id) as conn:
        conn.execute(
            "UPDATE agent_notifications SET status = %s, attempts = attempts + 1, "
            "last_attempt_at = %s, sent_at = %s, error = %s WHERE id = %s",
            (status, now, sent_at, error, notification_id),
        )


def handle_inbound(
    db: Database,
    sender: MessageSender,
    *,
    tenant_id: UUID,
    recipient_id: UUID,
    message_id: str,
    text: str,
    app_url: str,
    now: datetime,
    intent_llm: IntentLLM | None = None,
    nl_daily_cap: int = DEFAULT_DAILY_CAP,
) -> str | None:
    """Executa o pedido do socio e responde. Devolve o texto enviado, ou None se nao respondeu
    (mensagem ja tratada ou limite diario de respostas)."""
    command = parse_command(text)
    use_nl = command == "unknown" and intent_llm is not None
    with db.tenant_transaction(tenant_id) as conn:
        recent = conn.execute(
            "SELECT count(*) FROM agent_notifications WHERE recipient_id = %s AND kind = 'reply' "
            "AND created_at >= %s",
            (recipient_id, now - timedelta(hours=24)),
        ).fetchone()[0]
        if recent >= REPLY_CAP:
            return None
        claimed = conn.execute(
            "INSERT INTO agent_notifications (tenant_id, recipient_id, kind, dedupe_key, body, "
            "status, created_at) VALUES (%s, %s, 'reply', %s, '', 'pending', %s) "
            "ON CONFLICT (tenant_id, recipient_id, kind, dedupe_key) DO NOTHING RETURNING id",
            (tenant_id, recipient_id, message_id, now),
        ).fetchone()
        if claimed is None:
            return None  # reentrega do mesmo webhook: ja foi tratada
        zone = _tenant_zone(conn, tenant_id)
        reply = (
            None if use_nl else _respond(conn, tenant_id, command, recipient_id, zone, app_url, now)
        )
        if reply is not None:
            conn.execute(
                "UPDATE agent_notifications SET body = %s WHERE id = %s", (reply, claimed[0])
            )
        phone = conn.execute(
            "SELECT phone FROM agent_recipients WHERE id = %s", (recipient_id,)
        ).fetchone()[0]
    if use_nl:
        try:
            reply = natural_reply(
                db, tenant_id, recipient_id, intent_llm, text, app_url, now, nl_daily_cap
            )
        except Exception:
            logger.exception("agente em linguagem natural falhou")
            reply = unknown_text()
        with db.tenant_transaction(tenant_id) as conn:
            conn.execute(
                "UPDATE agent_notifications SET body = %s WHERE id = %s", (reply, claimed[0])
            )
    _send_reply(db, tenant_id, sender, claimed[0], phone, reply, now)
    return reply
