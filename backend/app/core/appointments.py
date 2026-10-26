"""Compromissos propostos a partir de mensagens classificadas como compromisso."""

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import psycopg

from app.core.schedule import When, extract_when
from app.db import Database

DEFAULT_TIMEZONE = "America/Sao_Paulo"


def _tenant_zone(conn: psycopg.Connection, tenant_id: UUID) -> ZoneInfo:
    row = conn.execute("SELECT timezone FROM tenants WHERE id = %s", (tenant_id,)).fetchone()
    try:
        return ZoneInfo(row[0] if row else DEFAULT_TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_TIMEZONE)


def insert_appointment(
    conn: psycopg.Connection,
    *,
    tenant_id: UUID,
    demand_id: UUID,
    contact_id: UUID | None,
    message_id: UUID,
    title: str,
    when: When,
) -> bool:
    """Grava o compromisso proposto. Uma mensagem gera no maximo um (idempotente)."""
    row = conn.execute(
        "INSERT INTO appointments (tenant_id, demand_id, contact_id, source_message_id, title, "
        "starts_at, all_day) VALUES (%s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (source_message_id) DO NOTHING RETURNING id",
        (tenant_id, demand_id, contact_id, message_id, title, when.start, when.all_day),
    ).fetchone()
    return row is not None


def propose_appointment(
    conn: psycopg.Connection,
    *,
    tenant_id: UUID,
    demand_id: UUID,
    contact_id: UUID | None,
    message_id: UUID,
    text: str | None,
    title: str,
    sent_at: datetime,
) -> bool:
    """Cria o compromisso (proposto) se a mensagem traz dia reconhecivel. Idempotente."""
    zone = _tenant_zone(conn, tenant_id)
    when = extract_when(text or "", sent_at.astimezone(zone))
    if when is None:
        return False
    return insert_appointment(
        conn,
        tenant_id=tenant_id,
        demand_id=demand_id,
        contact_id=contact_id,
        message_id=message_id,
        title=title,
        when=when,
    )


_BACKFILL = """
    SELECT m.id, dm.demand_id, m.contact_id, m.text, m.provider_timestamp
    FROM messages m
    JOIN demand_messages dm ON dm.message_id = m.id
    JOIN LATERAL (
        SELECT mc.* FROM message_classifications mc
        WHERE mc.message_id = m.id ORDER BY mc.created_at DESC, mc.id DESC LIMIT 1
    ) c ON true
    WHERE c.action = 'classified' AND c.kind = 'compromisso'
      AND NOT EXISTS (SELECT 1 FROM appointments a WHERE a.source_message_id = m.id)
    ORDER BY m.provider_timestamp
"""


def backfill_appointments(db: Database, tenant_id: UUID) -> int:
    """Propoe compromissos para mensagens que viraram demanda antes desta funcao existir."""
    from app.core.demands import make_title

    created = 0
    with db.tenant_transaction(tenant_id) as conn:
        for message_id, demand_id, contact_id, text, sent_at in conn.execute(_BACKFILL).fetchall():
            if propose_appointment(
                conn,
                tenant_id=tenant_id,
                demand_id=demand_id,
                contact_id=contact_id,
                message_id=message_id,
                text=text,
                title=make_title(text),
                sent_at=sent_at,
            ):
                created += 1
    return created
