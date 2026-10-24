"""Builders de payloads da Evolution API para os testes."""

from typing import Any

OFFICE_JID = "5511999990001@s.whatsapp.net"


def upsert_item(
    message_id: str = "3EB0A1",
    *,
    jid: str = "5511999990101@s.whatsapp.net",
    from_me: bool = False,
    message: dict[str, Any] | None = None,
    message_type: str | None = None,
    push_name: str | None = "Padaria Pao Quente",
    timestamp: int | str | None = 1760000000,
    key_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    key: dict[str, Any] = {"remoteJid": jid, "fromMe": from_me, "id": message_id}
    key.update(key_extra or {})
    item: dict[str, Any] = {
        "key": key,
        "message": message if message is not None else {"conversation": "Oi, tudo bem?"},
    }
    if push_name is not None:
        item["pushName"] = push_name
    if message_type is not None:
        item["messageType"] = message_type
    if timestamp is not None:
        item["messageTimestamp"] = timestamp
    return item


def upsert_payload(
    *items: dict[str, Any], event: str = "messages.upsert", instance: str = "escritorio"
) -> dict[str, Any]:
    data: Any = items[0] if len(items) == 1 else list(items)
    return {"event": event, "instance": instance, "data": data, "sender": OFFICE_JID}
