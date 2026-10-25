"""Monitor dos canais: estado da instancia na Evolution e reconciliacao das mensagens perdidas."""

import logging
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from app.db import Database
from app.evolution_client import EvolutionError
from app.ingestion.service import store_messages

logger = logging.getLogger(__name__)

FIRST_LOOKBACK = timedelta(hours=24)
MAX_LOOKBACK = timedelta(hours=72)
OVERLAP = timedelta(minutes=10)
MAX_PAGES = 10


class EvolutionLike(Protocol):
    def connection_state(self, instance: str) -> str: ...

    def find_messages(
        self, instance: str, *, since: datetime, until: datetime, page: int = 1, offset: int = 50
    ) -> tuple[list[dict[str, Any]], int]: ...


def _record_state(db: Database, tenant_id: UUID, channel_id: UUID, state: str) -> None:
    with db.tenant_transaction(tenant_id) as conn:
        conn.execute(
            "UPDATE channels SET health_state = %s, health_checked_at = now(), "
            "health_changed_at = CASE WHEN health_state IS DISTINCT FROM %s "
            "THEN now() ELSE health_changed_at END WHERE id = %s",
            (state, state, channel_id),
        )


def _reconcile(
    db: Database,
    evolution: EvolutionLike,
    channel: tuple[Any, ...],
    now: datetime,
) -> int:
    channel_id, tenant_id, instance, listen_groups, _, last_reconciled = channel
    since = (last_reconciled - OVERLAP) if last_reconciled else (now - FIRST_LOOKBACK)
    since = max(since, now - MAX_LOOKBACK)
    stored_total = 0
    page = 1
    while page <= MAX_PAGES:
        records, pages = evolution.find_messages(instance, since=since, until=now, page=page)
        stored = store_messages(db, tenant_id, channel_id, records, listen_groups=listen_groups)
        stored_total += stored.stored
        if page >= pages or stored.stored == 0:
            break
        page += 1
    with db.tenant_transaction(tenant_id) as conn:
        conn.execute("UPDATE channels SET last_reconciled_at = %s WHERE id = %s", (now, channel_id))
    return stored_total


def check_channels(
    db: Database, evolution: EvolutionLike, *, now: datetime | None = None
) -> Counter[str]:
    """Uma passada: confere o estado de cada canal e, estando conectado, busca o que faltou."""
    summary: Counter[str] = Counter()
    for channel in db.list_channels():
        channel_id, tenant_id, instance, _, previous, _ = channel
        moment = now or datetime.now(UTC)
        try:
            state = evolution.connection_state(instance)
            _record_state(db, tenant_id, channel_id, state)
            summary["checked"] += 1
            if state != previous and previous is not None:
                log = logger.warning if state == "open" else logger.error
                log("canal %s (instancia %s): %s -> %s", channel_id, instance, previous, state)
            if state != "open":
                continue
            summary["reconciled_stored"] += _reconcile(db, evolution, channel, moment)
        except EvolutionError:
            summary["reconcile_errors"] += 1
            logger.exception("reconciliacao falhou no canal %s", channel_id)
        except Exception:
            summary["errors"] += 1
            logger.exception("falha ao conferir o canal %s", channel_id)
    return summary
