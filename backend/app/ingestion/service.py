"""Gravacao das mensagens vindas da Evolution, pelo webhook ou pela reconciliacao."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.core.contacts import upsert_contact
from app.db import Database
from app.ingestion.evolution import parse_messages_upsert
from app.ingestion.repository import insert_message


@dataclass(frozen=True)
class StoreResult:
    received: int
    stored: int
    ignored: int


def store_messages(
    db: Database, tenant_id: UUID, channel_id: UUID, data: Any, *, listen_groups: bool
) -> StoreResult:
    """Grava as mensagens (idempotente) e conta as recebidas, as novas e as descartadas."""
    result = parse_messages_upsert(data, listen_groups=listen_groups)
    stored = 0
    with db.tenant_transaction(tenant_id) as conn:
        for message, raw in result.messages:
            contact_id = upsert_contact(
                conn,
                tenant_id=tenant_id,
                phone=message.contact_phone,
                push_name=message.push_name,
                incoming=message.direction == "in",
            )
            if insert_message(
                conn,
                tenant_id=tenant_id,
                channel_id=channel_id,
                contact_id=contact_id,
                message=message,
                raw=raw,
            ):
                stored += 1
    return StoreResult(len(result.messages), stored, len(result.ignored))
