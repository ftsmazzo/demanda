from datetime import UTC, datetime

from app.ingestion.evolution import parse_messages_upsert
from tests.factories import upsert_item


def parse(data, **kwargs):
    return parse_messages_upsert(data, **kwargs)


def test_plain_text_message_is_normalized():
    result = parse(upsert_item("A1", message={"conversation": "Oi"}))

    assert result.ignored == []
    [(msg, raw)] = result.messages
    assert msg.provider_message_id == "A1"
    assert msg.direction == "in"
    assert msg.remote_jid == "5511999990101@s.whatsapp.net"
    assert msg.contact_phone == "5511999990101"
    assert msg.push_name == "Padaria Pao Quente"
    assert msg.message_type == "conversation"
    assert msg.text == "Oi"
    assert msg.media is None
    assert msg.provider_timestamp == datetime.fromtimestamp(1760000000, UTC)
    assert raw["key"]["id"] == "A1"


def test_extended_text_message_uses_inner_text():
    item = upsert_item(message={"extendedTextMessage": {"text": "Segue o link"}})

    [(msg, _)] = parse(item).messages

    assert msg.message_type == "extendedTextMessage"
    assert msg.text == "Segue o link"


def test_image_keeps_caption_and_media_metadata():
    item = upsert_item(
        message={"imageMessage": {"caption": "NF de outubro", "mimetype": "image/jpeg"}},
    )

    [(msg, _)] = parse(item).messages

    assert msg.message_type == "imageMessage"
    assert msg.text == "NF de outubro"
    assert msg.media == {"mimetype": "image/jpeg"}


def test_audio_has_no_text_but_has_media():
    item = upsert_item(message={"audioMessage": {"mimetype": "audio/ogg", "seconds": 12}})

    [(msg, _)] = parse(item).messages

    assert msg.text is None
    assert msg.media == {"mimetype": "audio/ogg", "seconds": 12}


def test_from_me_is_outgoing():
    [(msg, _)] = parse(upsert_item(from_me=True)).messages

    assert msg.direction == "out"


def test_groups_are_ignored_by_default():
    result = parse(upsert_item(jid="120363000000000000@g.us"))

    assert result.messages == []
    assert result.ignored == ["group"]


def test_groups_are_kept_when_enabled_and_use_participant_phone():
    item = upsert_item(
        jid="120363000000000000@g.us",
        key_extra={"participant": "5511999990102@s.whatsapp.net"},
    )

    [(msg, _)] = parse(item, listen_groups=True).messages

    assert msg.contact_phone == "5511999990102"
    assert msg.remote_jid == "120363000000000000@g.us"


def test_status_broadcast_is_ignored():
    result = parse(upsert_item(jid="status@broadcast"))

    assert result.ignored == ["broadcast"]


def test_reaction_and_protocol_messages_are_ignored():
    reaction = upsert_item("R1", message={"reactionMessage": {"text": "ok"}})
    protocol = upsert_item("P1", message={"protocolMessage": {"type": 0}})

    result = parse([reaction, protocol])

    assert result.messages == []
    assert result.ignored == ["reaction", "protocol"]


def test_list_payload_returns_all_messages():
    result = parse([upsert_item("A1"), upsert_item("A2")])

    assert [m.provider_message_id for m, _ in result.messages] == ["A1", "A2"]


def test_item_without_id_is_ignored_as_malformed():
    item = upsert_item()
    del item["key"]["id"]

    result = parse(item)

    assert result.messages == []
    assert result.ignored == ["malformed"]


def test_item_without_message_body_is_ignored():
    item = upsert_item()
    del item["message"]

    assert parse(item).ignored == ["no_message"]


def test_lid_jid_prefers_alternate_phone_jid():
    item = upsert_item(
        jid="98765432109876@lid",
        key_extra={"remoteJidAlt": "5511999990103@s.whatsapp.net"},
    )

    [(msg, _)] = parse(item).messages

    assert msg.contact_phone == "5511999990103"


def test_timestamp_as_string_is_parsed():
    [(msg, _)] = parse(upsert_item(timestamp="1760000000")).messages

    assert msg.provider_timestamp == datetime.fromtimestamp(1760000000, UTC)


def test_missing_timestamp_falls_back_to_now_with_timezone():
    before = datetime.now(UTC)

    [(msg, _)] = parse(upsert_item(timestamp=None)).messages

    assert msg.provider_timestamp.tzinfo is not None
    assert msg.provider_timestamp >= before


def test_non_dict_items_are_ignored():
    assert parse(["texto solto", 42]).ignored == ["malformed", "malformed"]


def test_non_string_message_type_is_malformed():
    item = upsert_item()
    item["messageType"] = {"unexpected": "object"}

    result = parse(item)

    assert result.messages == []
    assert result.ignored == ["malformed"]


def test_nul_characters_and_media_blobs_are_scrubbed():
    item = upsert_item(
        message={
            "imageMessage": {
                "caption": "ol\x00a",
                "jpegThumbnail": "AAAA",
                "mimetype": "image/png",
            },
            "base64": "QUJD",
        },
        push_name="Jo\x00ao",
    )

    [(msg, raw)] = parse(item).messages

    assert msg.text == "ola"
    assert msg.push_name == "Joao"
    assert "base64" not in raw["message"]
    assert "jpegThumbnail" not in raw["message"]["imageMessage"]
    assert "\x00" not in str(raw)
