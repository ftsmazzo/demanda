"""Ciclo do agente: decide o que dizer aos socios (por SQL), grava na caixa de saida e envia."""

import logging
from collections import Counter
from datetime import datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg

from app.agent.messages import (
    AppointmentInfo,
    StuckItem,
    SummaryData,
    appointment_text,
    stuck_text,
    summary_text,
)
from app.agent.sender import MessageSender, SendError
from app.core.appointments import _tenant_zone
from app.db import Database

logger = logging.getLogger(__name__)

QUIET_BEFORE = 7  # nada sai antes das 07h nem a partir das 21h, na hora do escritorio
QUIET_FROM = 21
SUMMARY_FROM = 18
STUCK_FROM = 9
STUCK_ALERT_HOURS = 72
STUCK_SUMMARY_HOURS = 24
APPOINTMENT_WINDOW = timedelta(hours=24)
DAILY_CAP = 20  # avisos (nao respostas) por pessoa em 24 h
RETRY_AFTER = timedelta(minutes=5)
MAX_ATTEMPTS = 3

SECTOR_LABEL = {
    "fiscal": "Fiscal",
    "contabil": "Contábil",
    "dp": "Pessoal",
    "societario": "Societário",
    "financeiro": "Financeiro",
    "triagem": "Triagem",
    "rh-interno": "RH interno",
    "consultoria": "Consultoria",
}

_IDLE = "FLOOR(EXTRACT(EPOCH FROM (%s::timestamptz - d.last_activity_at)) / 3600)::int"


def _enqueue(
    conn: psycopg.Connection,
    tenant_id: UUID,
    recipient_id: UUID,
    kind: str,
    key: str,
    body: str,
    now: datetime,
) -> None:
    """Poe o aviso na caixa de saida. Sem texto vira 'skipped' (nada a dizer). No limite diario
    nao grava nada: o aviso espera e sai quando houver folga, em vez de se perder."""
    if body:
        recent = conn.execute(
            "SELECT count(*) FROM agent_notifications WHERE recipient_id = %s "
            "AND kind <> 'reply' AND status IN ('sent', 'dry_run') AND created_at >= %s",
            (recipient_id, now - timedelta(hours=24)),
        ).fetchone()[0]
        if recent >= DAILY_CAP:
            logger.info("limite diario de avisos atingido para o destinatario %s", recipient_id)
            return
    conn.execute(
        "INSERT INTO agent_notifications (tenant_id, recipient_id, kind, dedupe_key, body, status, "
        "created_at) VALUES (%s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (tenant_id, recipient_id, kind, dedupe_key) DO NOTHING",
        (tenant_id, recipient_id, kind, key, body, "pending" if body else "skipped", now),
    )


def _missing(conn: psycopg.Connection, recipients: list, kind: str, key: str) -> list:
    done = {
        row[0]
        for row in conn.execute(
            "SELECT recipient_id FROM agent_notifications WHERE kind = %s AND dedupe_key = %s",
            (kind, key),
        )
    }
    return [recipient for recipient in recipients if recipient[0] not in done]


def _plan_appointments(conn, tenant_id, recipients, zone, app_url, now) -> None:
    rows = conn.execute(
        "SELECT a.id, a.title, a.starts_at, a.all_day, c.name, d.sector "
        "FROM appointments a JOIN demands d ON d.id = a.demand_id "
        "LEFT JOIN contacts c ON c.id = a.contact_id "
        "WHERE a.status = 'proposed' AND a.created_at >= %s ORDER BY a.created_at, a.id",
        (now - APPOINTMENT_WINDOW,),
    ).fetchall()
    for appointment_id, title, starts_at, all_day, contact, sector in rows:
        info = AppointmentInfo(
            title, starts_at.astimezone(zone), all_day, contact, SECTOR_LABEL.get(sector, sector)
        )
        body = appointment_text(info, app_url)
        for recipient_id, _ in recipients:
            _enqueue(conn, tenant_id, recipient_id, "appointment", str(appointment_id), body, now)


def stuck_items(
    conn: psycopg.Connection, now: datetime, minimum: int, limit: int
) -> list[StuckItem]:
    rows = conn.execute(
        f"SELECT d.title, d.sector, {_IDLE} AS idle, COALESCE(c.priority, false) "
        "FROM demands d LEFT JOIN contacts c ON c.id = d.contact_id "
        "WHERE d.status <> 'concluido' AND "
        f"{_IDLE} >= CASE WHEN COALESCE(c.priority, false) THEN LEAST(%s, 24) ELSE %s END "
        "ORDER BY idle DESC, d.id LIMIT %s",
        (now, now, minimum, minimum, limit),
    ).fetchall()
    return [
        StuckItem(title, SECTOR_LABEL.get(sector, sector), idle, vip)
        for title, sector, idle, vip in rows
    ]


def _summary_data(conn: psycopg.Connection, zone: ZoneInfo, now: datetime) -> SummaryData:
    local = now.astimezone(zone)
    start = datetime.combine(local.date(), time.min, tzinfo=zone)
    end = start + timedelta(days=1)
    created, closed, open_total, critical = conn.execute(
        "SELECT count(*) FILTER (WHERE created_at >= %s AND created_at < %s), "
        "count(*) FILTER (WHERE closed_at >= %s AND closed_at < %s), "
        "count(*) FILTER (WHERE status <> 'concluido'), "
        "count(*) FILTER (WHERE status <> 'concluido' AND urgency = 'critica') FROM demands",
        (start, end, start, end),
    ).fetchone()
    tomorrow = [
        ("dia todo" if all_day else starts_at.astimezone(zone).strftime("%H:%M"), title)
        for title, starts_at, all_day in conn.execute(
            "SELECT title, starts_at, all_day FROM appointments WHERE status <> 'cancelled' "
            "AND starts_at >= %s AND starts_at < %s ORDER BY starts_at, id",
            (end, end + timedelta(days=1)),
        )
    ]
    stuck = stuck_items(conn, now, STUCK_SUMMARY_HOURS, 3)
    return SummaryData(local.date(), created, closed, open_total, critical, stuck, tomorrow)


def _plan_summary(conn, tenant_id, recipients, zone, app_url, now) -> None:
    key = now.astimezone(zone).date().isoformat()
    missing = _missing(conn, recipients, "daily_summary", key)
    if not missing:
        return
    data = _summary_data(conn, zone, now)
    quiet = not (data.created_today or data.closed_today or data.open_total)
    body = "" if quiet else summary_text(data, app_url)
    for recipient_id, _ in missing:
        _enqueue(conn, tenant_id, recipient_id, "daily_summary", key, body, now)


def _plan_stuck(conn, tenant_id, recipients, zone, app_url, now) -> None:
    key = now.astimezone(zone).date().isoformat()
    missing = _missing(conn, recipients, "stuck", key)
    if not missing:
        return
    items = stuck_items(conn, now, STUCK_ALERT_HOURS, 5)
    body = stuck_text(items, app_url) if items else ""
    for recipient_id, _ in missing:
        _enqueue(conn, tenant_id, recipient_id, "stuck", key, body, now)


_NEXT_DELIVERY = (
    "SELECT n.id, n.body, r.phone FROM agent_notifications n "
    "JOIN agent_recipients r ON r.id = n.recipient_id AND r.active "
    "WHERE n.status IN ('pending', 'failed') AND n.kind <> 'reply' AND n.attempts < %s "
    "AND (n.last_attempt_at IS NULL OR n.last_attempt_at <= %s) "
    "ORDER BY n.created_at, n.id LIMIT 1 FOR UPDATE OF n SKIP LOCKED"
)


def _deliver(db: Database, tenant_id: UUID, sender: MessageSender, now: datetime) -> Counter[str]:
    counts: Counter[str] = Counter()
    while True:
        with db.tenant_transaction(tenant_id) as conn:
            row = conn.execute(_NEXT_DELIVERY, (MAX_ATTEMPTS, now - RETRY_AFTER)).fetchone()
            if row is None:
                return counts
            notification_id, body, phone = row
            try:
                sender.send(phone, body)
            except SendError as exc:
                conn.execute(
                    "UPDATE agent_notifications SET status = 'failed', attempts = attempts + 1, "
                    "last_attempt_at = %s, error = %s WHERE id = %s",
                    (now, str(exc)[:200], notification_id),
                )
                counts["failed"] += 1
                logger.error("aviso %s nao enviado: %s", notification_id, exc)
            else:
                conn.execute(
                    "UPDATE agent_notifications SET status = %s, attempts = attempts + 1, "
                    "last_attempt_at = %s, sent_at = %s, error = NULL WHERE id = %s",
                    (sender.mode, now, now, notification_id),
                )
                counts[sender.mode] += 1


def run_tenant(
    db: Database, tenant_id: UUID, sender: MessageSender, *, app_url: str, now: datetime
) -> Counter[str]:
    """Planeja e envia os avisos de um tenant. Fora das 07h-21h locais nao faz nada."""
    with db.tenant_transaction(tenant_id) as conn:
        recipients = conn.execute(
            "SELECT id, phone FROM agent_recipients WHERE active ORDER BY created_at, id"
        ).fetchall()
        if not recipients:
            return Counter()
        zone = _tenant_zone(conn, tenant_id)
        local = now.astimezone(zone)
        if not QUIET_BEFORE <= local.hour < QUIET_FROM:
            return Counter()
        _plan_appointments(conn, tenant_id, recipients, zone, app_url, now)
        if local.weekday() < 5 and local.hour >= SUMMARY_FROM:
            _plan_summary(conn, tenant_id, recipients, zone, app_url, now)
        if local.weekday() < 5 and local.hour >= STUCK_FROM:
            _plan_stuck(conn, tenant_id, recipients, zone, app_url, now)
    return _deliver(db, tenant_id, sender, now)
