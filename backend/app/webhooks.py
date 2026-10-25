import hmac
import logging
from hashlib import sha256
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Body, Header, HTTPException, Request

from app.db import Database
from app.ingestion.evolution import UPSERT_EVENT, normalize_event
from app.ingestion.service import store_messages

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

    result = store_messages(
        db, auth.tenant_id, channel_id, payload.get("data"), listen_groups=auth.listen_groups
    )
    received, stored = result.received, result.stored
    logger.info(
        "webhook channel=%s received=%d stored=%d duplicates=%d ignored=%d",
        channel_id,
        received,
        stored,
        received - stored,
        result.ignored,
    )
    return {
        "received": received,
        "stored": stored,
        "duplicates": received - stored,
        "ignored": result.ignored,
    }
