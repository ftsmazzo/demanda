"""Normaliza o evento messages.upsert da Evolution API em mensagens do dominio."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, NamedTuple

logger = logging.getLogger(__name__)

UPSERT_EVENT = "messages.upsert"

_IGNORED_TYPES = {
    "protocolMessage": "protocol",
    "reactionMessage": "reaction",
    "senderKeyDistributionMessage": "protocol",
}
_NON_CONTENT_KEYS = {"messageContextInfo", "senderKeyDistributionMessage"}
_CAPTION_TYPES = {"imageMessage", "videoMessage", "documentMessage"}
_MEDIA_TYPES = _CAPTION_TYPES | {"audioMessage", "stickerMessage"}
_MEDIA_FIELDS = ("mimetype", "fileName", "seconds", "fileLength")
# blobs que incham o banco sem valor para o produto
_DROPPED_KEYS = {"base64", "jpegThumbnail"}


@dataclass(frozen=True, slots=True)
class IncomingMessage:
    provider_message_id: str
    direction: str
    remote_jid: str
    contact_phone: str
    push_name: str | None
    message_type: str
    text: str | None
    media: dict[str, Any] | None
    provider_timestamp: datetime


class ParseResult(NamedTuple):
    messages: list[tuple[IncomingMessage, dict[str, Any]]]
    ignored: list[str]


def scrub(value: Any) -> Any:
    """Remove NUL (que o Postgres rejeita em text e jsonb) e blobs base64 do payload."""
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, dict):
        return {scrub(k): scrub(v) for k, v in value.items() if k not in _DROPPED_KEYS}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


def normalize_event(event: object) -> str:
    return str(event or "").strip().lower().replace("_", ".")


def parse_messages_upsert(data: Any, *, listen_groups: bool = False) -> ParseResult:
    """Converte o campo data do webhook (objeto ou lista) em mensagens e motivos de descarte."""
    items = data if isinstance(data, list) else [data]
    messages: list[tuple[IncomingMessage, dict[str, Any]]] = []
    ignored: list[str] = []
    for raw_item in items:
        item = scrub(raw_item)
        parsed = _parse_item(item, listen_groups=listen_groups)
        if isinstance(parsed, str):
            ignored.append(parsed)
        else:
            messages.append((parsed, item))
    return ParseResult(messages, ignored)


def _parse_item(item: Any, *, listen_groups: bool) -> IncomingMessage | str:
    if not isinstance(item, dict):
        return "malformed"
    key = item.get("key")
    if not isinstance(key, dict) or not key.get("id") or not key.get("remoteJid"):
        return "malformed"

    jid = str(key["remoteJid"])
    if jid.endswith("@broadcast"):
        return "broadcast"
    is_group = jid.endswith("@g.us")
    if is_group and not listen_groups:
        return "group"

    body = item.get("message")
    if not isinstance(body, dict) or not body:
        return "no_message"
    message_type = item.get("messageType") or _first_content_key(body)
    if message_type is None:
        return "no_message"
    if not isinstance(message_type, str):
        return "malformed"
    if message_type in _IGNORED_TYPES:
        return _IGNORED_TYPES[message_type]

    return IncomingMessage(
        provider_message_id=str(key["id"]),
        direction="out" if key.get("fromMe") else "in",
        remote_jid=jid,
        contact_phone=_contact_phone(key, jid, is_group=is_group),
        push_name=item.get("pushName") or None,
        message_type=str(message_type),
        text=_extract_text(message_type, body),
        media=_extract_media(message_type, body),
        provider_timestamp=_parse_timestamp(item.get("messageTimestamp")),
    )


def _first_content_key(body: dict[str, Any]) -> str | None:
    return next((k for k in body if k not in _NON_CONTENT_KEYS), None)


def _digits(jid: str) -> str:
    return jid.split("@", 1)[0].split(":", 1)[0]


def _contact_phone(key: dict[str, Any], jid: str, *, is_group: bool) -> str:
    if is_group and key.get("participant"):
        return _digits(str(key["participant"]))
    if jid.endswith("@lid") and key.get("remoteJidAlt"):
        return _digits(str(key["remoteJidAlt"]))
    return _digits(jid)


def _extract_text(message_type: str, body: dict[str, Any]) -> str | None:
    if message_type == "conversation":
        return _as_text(body.get("conversation"))
    inner = body.get(message_type)
    if not isinstance(inner, dict):
        return None
    if message_type == "extendedTextMessage":
        return _as_text(inner.get("text"))
    if message_type in _CAPTION_TYPES:
        return _as_text(inner.get("caption"))
    return None


def _as_text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _extract_media(message_type: str, body: dict[str, Any]) -> dict[str, Any] | None:
    if message_type not in _MEDIA_TYPES:
        return None
    inner = body.get(message_type)
    if not isinstance(inner, dict):
        return None
    media = {field: inner[field] for field in _MEDIA_FIELDS if field in inner}
    return media or None


def _parse_timestamp(value: Any) -> datetime:
    try:
        return datetime.fromtimestamp(int(value), UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        logger.warning("messageTimestamp ausente ou invalido; usando o horario de recebimento")
        return datetime.now(UTC)
