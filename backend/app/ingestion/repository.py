from typing import Any
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from app.ingestion.evolution import IncomingMessage

_INSERT = """
    INSERT INTO messages (
        tenant_id, channel_id, provider_message_id, direction, remote_jid, contact_phone,
        push_name, message_type, text, media, provider_timestamp, raw, contact_id
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (channel_id, provider_message_id) DO NOTHING
    RETURNING id
"""


def insert_message(
    conn: psycopg.Connection,
    *,
    tenant_id: UUID,
    channel_id: UUID,
    contact_id: UUID,
    message: IncomingMessage,
    raw: dict[str, Any],
) -> bool:
    """Grava a mensagem bruta. Devolve False quando ela ja existia (reentrega)."""
    row = conn.execute(
        _INSERT,
        (
            tenant_id,
            channel_id,
            message.provider_message_id,
            message.direction,
            message.remote_jid,
            message.contact_phone,
            message.push_name,
            message.message_type,
            message.text,
            Jsonb(message.media) if message.media is not None else None,
            message.provider_timestamp,
            Jsonb(raw),
            contact_id,
        ),
    ).fetchone()
    return row is not None
