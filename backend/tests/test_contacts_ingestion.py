from tests.conftest import ChannelFixture
from tests.factories import upsert_item, upsert_payload
from tests.test_webhook import post

PHONE = "5511999990101"
JID = f"{PHONE}@s.whatsapp.net"


def contacts_of(admin_conn, tenant_id):
    return admin_conn.execute(
        "SELECT phone, name, kind FROM contacts WHERE tenant_id = %s ORDER BY phone", (tenant_id,)
    ).fetchall()


def test_incoming_message_creates_the_contact_and_links_it(client, admin_conn, channel):
    post(
        client, channel, upsert_payload(upsert_item("K1", jid=JID, push_name="Padaria Pao Quente"))
    )

    assert contacts_of(admin_conn, channel.tenant_id) == [
        (PHONE, "Padaria Pao Quente", "desconhecido")
    ]
    linked = admin_conn.execute(
        "SELECT count(*) FROM messages m JOIN contacts c ON c.id = m.contact_id "
        "WHERE m.channel_id = %s AND c.phone = %s",
        (channel.channel_id, PHONE),
    ).fetchone()[0]
    assert linked == 1


def test_the_same_phone_reuses_the_contact(client, admin_conn, channel):
    post(client, channel, upsert_payload(upsert_item("K2", jid=JID)))
    post(client, channel, upsert_payload(upsert_item("K3", jid=JID)))

    assert len(contacts_of(admin_conn, channel.tenant_id)) == 1


def test_redelivery_does_not_create_extra_contacts_or_messages(client, admin_conn, channel):
    payload = upsert_payload(upsert_item("K4", jid=JID))

    post(client, channel, payload)
    post(client, channel, payload)

    assert len(contacts_of(admin_conn, channel.tenant_id)) == 1


def test_outgoing_message_does_not_name_the_contact_with_our_own_name(client, admin_conn, channel):
    post(
        client,
        channel,
        upsert_payload(upsert_item("K5", jid=JID, from_me=True, push_name="Escritorio")),
    )

    assert contacts_of(admin_conn, channel.tenant_id) == [(PHONE, None, "desconhecido")]


def test_a_later_incoming_message_fills_a_missing_name(client, admin_conn, channel):
    post(
        client,
        channel,
        upsert_payload(upsert_item("K6", jid=JID, from_me=True, push_name="Escritorio")),
    )
    post(client, channel, upsert_payload(upsert_item("K7", jid=JID, push_name="Clinica Vida")))

    assert contacts_of(admin_conn, channel.tenant_id)[0][1] == "Clinica Vida"


def test_a_name_set_by_a_person_is_never_overwritten(client, admin_conn, channel):
    post(client, channel, upsert_payload(upsert_item("K8", jid=JID, push_name="Primeiro Nome")))
    admin_conn.execute(
        "UPDATE contacts SET name = 'Nome Manual' WHERE tenant_id = %s", (channel.tenant_id,)
    )

    post(client, channel, upsert_payload(upsert_item("K9", jid=JID, push_name="Outro Apelido")))

    assert contacts_of(admin_conn, channel.tenant_id)[0][1] == "Nome Manual"


def test_the_same_phone_in_two_tenants_gives_two_separate_contacts(
    client, admin_conn, channel: ChannelFixture, other_channel: ChannelFixture
):
    post(client, channel, upsert_payload(upsert_item("K10", jid=JID, push_name="Cliente A")))
    post(client, other_channel, upsert_payload(upsert_item("K11", jid=JID, push_name="Cliente B")))

    assert contacts_of(admin_conn, channel.tenant_id)[0][1] == "Cliente A"
    assert contacts_of(admin_conn, other_channel.tenant_id)[0][1] == "Cliente B"
