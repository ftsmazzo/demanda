"""Webhook da instancia do agente: as mensagens que os socios mandam para ele."""

import hmac
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Annotated, Any

from fastapi import APIRouter, Body, Header, HTTPException, Request

from app.agent.inbound import handle_inbound
from app.agent.sender import MessageSender
from app.db import Database
from app.ingestion.evolution import UPSERT_EVENT, normalize_event, parse_messages_upsert

logger = logging.getLogger(__name__)

router = APIRouter()

_MAX_ECHOED_EVENT = 64
_BR_MOBILE = re.compile(r"^55(\d{2})9(\d{8})$")
_BR_OLD = re.compile(r"^55(\d{2})(\d{8})$")


@dataclass(frozen=True)
class AgentRuntime:
    sender: MessageSender
    secret_hash: str
    app_url: str


def make_runtime(sender: MessageSender, secret: str, app_url: str) -> AgentRuntime:
    return AgentRuntime(sender, sha256(secret.encode()).hexdigest(), app_url)


def phone_variants(phone: str) -> list[str]:
    """O WhatsApp as vezes entrega celular brasileiro sem o 9: aceita as duas formas."""
    variants = [phone]
    mobile, old = _BR_MOBILE.match(phone), _BR_OLD.match(phone)
    if mobile:
        variants.append(f"55{mobile.group(1)}{mobile.group(2)}")
    elif old:
        variants.append(f"55{old.group(1)}9{old.group(2)}")
    return variants


@router.post("/webhooks/agent")
def agent_webhook(
    request: Request,
    payload: Annotated[dict[str, Any], Body()],
    x_webhook_secret: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    runtime: AgentRuntime | None = request.app.state.agent
    db: Database | None = request.app.state.db
    if runtime is None or db is None:
        raise HTTPException(status_code=404, detail="Not Found")
    given = sha256((x_webhook_secret or "").encode()).hexdigest()
    if not x_webhook_secret or not hmac.compare_digest(given, runtime.secret_hash):
        logger.warning("webhook do agente: segredo invalido")
        raise HTTPException(status_code=401, detail="unauthorized")

    event = normalize_event(payload.get("event"))
    if event != UPSERT_EVENT:
        return {"status": "ignored", "event": event[:_MAX_ECHOED_EVENT]}

    handled = 0
    for message, _ in parse_messages_upsert(payload.get("data"), listen_groups=False).messages:
        if message.direction != "in" or not message.text:
            continue
        found = {
            row
            for variant in phone_variants(message.contact_phone)
            for row in db.agent_recipients_by_phone(variant)
        }
        if len(found) != 1:
            # desconhecido: ignora em silencio; em mais de uma empresa: nao adivinha
            logger.warning(
                "mensagem ao agente de numero final %s: %d destinatario(s) encontrado(s)",
                message.contact_phone[-4:],
                len(found),
            )
            continue
        recipient_id, tenant_id = next(iter(found))
        reply = handle_inbound(
            db,
            runtime.sender,
            tenant_id=tenant_id,
            recipient_id=recipient_id,
            message_id=message.provider_message_id,
            text=message.text,
            app_url=runtime.app_url,
            now=datetime.now(UTC),
        )
        handled += reply is not None
    return {"handled": handled}
