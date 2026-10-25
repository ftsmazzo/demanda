"""Transforma mensagens classificadas em demandas (e agrupa as que seguem o mesmo assunto)."""

import logging
from collections import Counter
from typing import Any
from uuid import UUID

import psycopg

from app.classification.domain import max_urgency
from app.db import Database

logger = logging.getLogger(__name__)

TITLE_MAX_CHARS = 80
NO_TEXT_TITLE = "Mensagem sem texto"

# Ultima classificacao de cada mensagem que ainda nao esta ligada a nenhuma demanda.
_PENDING = """
    SELECT m.id, m.contact_id, m.text, m.provider_timestamp,
           c.action, c.sector, c.kind, c.urgency
    FROM messages m
    JOIN LATERAL (
        SELECT mc.* FROM message_classifications mc
        WHERE mc.message_id = m.id
        ORDER BY mc.created_at DESC, mc.id DESC
        LIMIT 1
    ) c ON true
    WHERE c.action IN ('classified', 'attach_reply')
      AND m.contact_id IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM demand_messages dm WHERE dm.message_id = m.id)
      AND NOT EXISTS (SELECT 1 FROM skipped_messages sk WHERE sk.message_id = m.id)
    ORDER BY m.provider_timestamp, m.id
    LIMIT %s
"""

_OPEN_BY_SECTOR = """
    SELECT id, urgency FROM demands
    WHERE contact_id = %s AND sector = %s AND status <> 'concluido'
    ORDER BY last_activity_at DESC, id DESC
    LIMIT 1
"""

_LATEST_OPEN = """
    SELECT id, urgency FROM demands
    WHERE contact_id = %s AND status <> 'concluido'
    ORDER BY last_activity_at DESC, id DESC
    LIMIT 1
"""

_CREATE = """
    INSERT INTO demands (tenant_id, contact_id, sector, kind, urgency, title, last_activity_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    RETURNING id
"""

_LINK = "INSERT INTO demand_messages (tenant_id, demand_id, message_id) VALUES (%s, %s, %s)"

_TOUCH = """
    UPDATE demands
    SET urgency = %s, last_activity_at = GREATEST(last_activity_at, %s), updated_at = now()
    WHERE id = %s
"""


def make_title(text: str | None) -> str:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return NO_TEXT_TITLE
    if len(cleaned) > TITLE_MAX_CHARS:
        return cleaned[:TITLE_MAX_CHARS].rstrip() + "..."
    return cleaned


def materialize_demands(db: Database, tenant_id: UUID, *, limit: int = 200) -> Counter[str]:
    """Cria ou atualiza demandas a partir das classificacoes ainda nao ligadas a uma demanda.

    Uma mensagem entra na demanda aberta do mesmo contato e setor (ou, se for so um "ok", na
    demanda aberta mais recente do contato); sem demanda aberta, abre uma nova. Demanda
    concluida nunca e reaberta. Cada mensagem tem a propria transacao: uma falha nao trava as
    outras (conta em "failed") e a mensagem e tentada de novo na proxima execucao.
    """
    with db.tenant_transaction(tenant_id) as conn:
        pending = conn.execute(_PENDING, (limit,)).fetchall()

    counts: Counter[str] = Counter()
    for row in pending:
        try:
            with db.tenant_transaction(tenant_id) as conn:
                outcome = _materialize_one(conn, tenant_id, row)
        except Exception:
            logger.exception("falha ao criar demanda para a mensagem %s", row[0])
            counts["failed"] += 1
            continue
        counts[outcome] += 1
    return counts


def _materialize_one(conn: psycopg.Connection, tenant_id: UUID, row: tuple[Any, ...]) -> str:
    message_id, contact_id, text, sent_at, action, sector, kind, urgency = row

    # uma execucao por contato de cada vez: evita demandas duplicadas quando ha concorrencia
    conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (str(contact_id),))
    if conn.execute(
        "SELECT 1 FROM demand_messages WHERE message_id = %s", (message_id,)
    ).fetchone():
        return "already"

    if action == "attach_reply":
        found = conn.execute(_LATEST_OPEN, (contact_id,)).fetchone()
    else:
        found = conn.execute(_OPEN_BY_SECTOR, (contact_id, sector)).fetchone()

    if found is not None:
        demand_id, current_urgency = found
        new_urgency = (
            max_urgency(current_urgency, urgency) if action != "attach_reply" else current_urgency
        )
        conn.execute(_LINK, (tenant_id, demand_id, message_id))
        conn.execute(_TOUCH, (new_urgency, sent_at, demand_id))
        return "attached"

    if action == "attach_reply":
        conn.execute(
            "INSERT INTO skipped_messages (tenant_id, message_id, reason) "
            "VALUES (%s, %s, 'attach_without_open_demand') ON CONFLICT DO NOTHING",
            (tenant_id, message_id),
        )
        return "skipped"

    demand_id = conn.execute(
        _CREATE, (tenant_id, contact_id, sector, kind, urgency, make_title(text), sent_at)
    ).fetchone()[0]
    conn.execute(_LINK, (tenant_id, demand_id, message_id))
    return "created"
