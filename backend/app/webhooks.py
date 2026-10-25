import hmac
import logging
from hashlib import sha256
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Body, Header, HTTPException, Request

from app.core.contacts import upsert_contact
from app.db import Database
from app.ingestion.evolution import UPSERT_EVENT, normalize_event, parse_messages_upsert
from app.ingestion.repository import insert_message

logger = logging.getLogger(__name__)

router = APIRouter()

_UNKNOWN_SECRET_HASH = "0" * 64
_MAX_ECHOED_EVENT = 64


@router.post("/webhooks/evolution/{channel_id}")
def evolution_webhook(
    channel_id: UUID,
    request: Request,
    payload: Annotated[dict[str, Any], Body()],
    x_webhook_secret: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    db: Database | None = request.app.state.db
    if db is None:
        raise HTTPException(status_code=503, detail="database unavailable")

    auth = db.auth_channel(channel_id)
    # compara sempre, mesmo com canal inexistente, para nao diferenciar os casos
    expected = auth.webhook_secret_hash if auth else _UNKNOWN_SECRET_HASH
    given = sha256((x_webhook_secret or "").encode()).hexdigest()
    secret_ok = hmac.compare_digest(given, expected)
    if auth is None or not x_webhook_secret or not secret_ok:
        logger.warning("webhook auth failed channel=%s", channel_id)
        raise HTTPException(status_code=401, detail="unauthorized")

    event = normalize_event(payload.get("event"))
    if event != UPSERT_EVENT:
        return {"status": "ignored", "event": event[:_MAX_ECHOED_EVENT]}

    result = parse_messages_upsert(payload.get("data"), listen_groups=auth.listen_groups)
    stored = 0
    with db.tenant_transaction(auth.tenant_id) as conn:
        for message, raw in result.messages:
            contact_id = upsert_contact(
                conn,
                tenant_id=auth.tenant_id,
                phone=message.contact_phone,
                push_name=message.push_name,
                incoming=message.direction == "in",
            )
            if insert_message(
                conn,
                tenant_id=auth.tenant_id,
                channel_id=channel_id,
                contact_id=contact_id,
                message=message,
                raw=raw,
            ):
                stored += 1

    received = len(result.messages)
    logger.info(
        "webhook channel=%s received=%d stored=%d duplicates=%d ignored=%d",
        channel_id,
        received,
        stored,
        received - stored,
        len(result.ignored),
    )
    return {
        "received": received,
        "stored": stored,
        "duplicates": received - stored,
        "ignored": len(result.ignored),
    }
