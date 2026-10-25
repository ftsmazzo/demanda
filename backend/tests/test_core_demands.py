from datetime import timedelta

from app.classification.store import classify_pending
from app.core.demands import materialize_demands
from tests.test_classification_store import BASE, add_message
from tests.test_core_schema import make_demand

LONG_TEXT = "Preciso da guia do DAS " + "x" * 200


def process(database, tenant_id):
    classify_pending(database, tenant_id)
    return materialize_demands(database, tenant_id)


def demands_of(admin_conn, tenant_id):
    return admin_conn.execute(
        "SELECT sector, kind, urgency, status, origin, title, contact_id, last_activity_at, id "
        "FROM demands WHERE tenant_id = %s ORDER BY created_at, id",
        (tenant_id,),
    ).fetchall()


def contact_of(admin_conn, message_id):
    return admin_conn.execute(
        "SELECT contact_id FROM messages WHERE id = %s", (message_id,)
    ).fetchone()[0]


def linked_messages(admin_conn, demand_id):
    rows = admin_conn.execute(
        "SELECT message_id FROM demand_messages WHERE demand_id = %s", (demand_id,)
    ).fetchall()
    return {row[0] for row in rows}


def test_a_classified_message_becomes_a_demand_linked_to_it(database, admin_conn, channel):
    message = add_message(admin_conn, channel, "D1", "Quando vence o DAS esse mes?", minutes=3)

    counts = process(database, channel.tenant_id)

    [row] = demands_of(admin_conn, channel.tenant_id)
    sector, kind, urgency, status, origin, title, contact_id, activity, demand_id = row
    assert counts["created"] == 1
    assert (sector, kind, urgency, status, origin) == ("fiscal", "duvida", "normal", "novo", "auto")
    assert title == "Quando vence o DAS esse mes?"
    assert contact_id == contact_of(admin_conn, message)
    assert activity == BASE + timedelta(minutes=3)
    assert linked_messages(admin_conn, demand_id) == {message}


def test_a_second_message_on_the_same_topic_joins_the_open_demand(database, admin_conn, channel):
    add_message(admin_conn, channel, "D2", "Quando vence o DAS esse mes?", minutes=0)
    add_message(admin_conn, channel, "D3", "Urgente, preciso da guia do DAS hoje", minutes=30)

    counts = process(database, channel.tenant_id)

    [row] = demands_of(admin_conn, channel.tenant_id)
    assert counts["created"] == 1
    assert counts["attached"] == 1
    assert row[2] == "alta"
    assert row[7] == BASE + timedelta(minutes=30)
    assert len(linked_messages(admin_conn, row[8])) == 2


def test_another_sector_opens_a_separate_demand(database, admin_conn, channel):
    add_message(admin_conn, channel, "D4", "Quando vence o DAS esse mes?", minutes=0)
    add_message(admin_conn, channel, "D5", "Preciso da folha de pagamento de outubro", minutes=1)

    process(database, channel.tenant_id)

    sectors = sorted(row[0] for row in demands_of(admin_conn, channel.tenant_id))
    assert sectors == ["dp", "fiscal"]


def test_another_contact_opens_a_separate_demand(database, admin_conn, channel):
    add_message(admin_conn, channel, "D6", "Quando vence o DAS esse mes?", phone="5511999990101")
    add_message(admin_conn, channel, "D7", "Quando vence o DAS esse mes?", phone="5511999990102")

    process(database, channel.tenant_id)

    assert len(demands_of(admin_conn, channel.tenant_id)) == 2


def test_a_closed_demand_is_not_reopened_by_a_new_message(database, admin_conn, channel):
    first = add_message(admin_conn, channel, "D8", "Quando vence o DAS esse mes?", minutes=0)
    make_demand(
        admin_conn, channel.tenant_id, contact_id=contact_of(admin_conn, first), status="concluido"
    )

    process(database, channel.tenant_id)

    statuses = sorted(row[3] for row in demands_of(admin_conn, channel.tenant_id))
    assert statuses == ["concluido", "novo"]


def test_acknowledgement_attaches_to_the_latest_open_demand_of_the_contact(
    database, admin_conn, channel
):
    first = add_message(admin_conn, channel, "D9", "Quando vence o DAS esse mes?", minutes=0)
    process(database, channel.tenant_id)
    ack = add_message(admin_conn, channel, "D10", "ok", minutes=60)

    counts = process(database, channel.tenant_id)

    [row] = demands_of(admin_conn, channel.tenant_id)
    assert counts["attached"] == 1
    assert row[7] == BASE + timedelta(minutes=60)
    assert linked_messages(admin_conn, row[8]) == {first, ack}


def test_noise_and_outgoing_messages_create_no_demand(database, admin_conn, channel):
    add_message(admin_conn, channel, "D11", "Bom dia!")
    add_message(admin_conn, channel, "D12", "Segue a guia", direction="out", minutes=1)

    counts = process(database, channel.tenant_id)

    assert demands_of(admin_conn, channel.tenant_id) == []
    assert sum(counts.values()) == 0


def test_a_message_that_needs_review_still_gets_a_demand_in_triage(database, admin_conn, channel):
    add_message(admin_conn, channel, "D13", "Pode me ajudar com uma coisa aqui?")

    process(database, channel.tenant_id)

    [row] = demands_of(admin_conn, channel.tenant_id)
    assert row[0] == "triagem"


def test_running_twice_does_not_duplicate_demands_or_links(database, admin_conn, channel):
    add_message(admin_conn, channel, "D14", "Quando vence o DAS esse mes?")

    process(database, channel.tenant_id)
    second = materialize_demands(database, channel.tenant_id)

    assert sum(second.values()) == 0
    assert len(demands_of(admin_conn, channel.tenant_id)) == 1


def test_long_titles_are_shortened_and_empty_text_gets_a_placeholder(database, admin_conn, channel):
    add_message(admin_conn, channel, "D15", LONG_TEXT, phone="5511999990101")
    add_message(admin_conn, channel, "D16", None, phone="5511999990102", media=True)

    process(database, channel.tenant_id)

    titles = sorted((row[5] for row in demands_of(admin_conn, channel.tenant_id)), key=len)
    assert titles[0] == "Mensagem sem texto"
    assert len(titles[1]) <= 90
    assert titles[1].endswith("...")


def test_materializing_one_tenant_never_touches_another(
    database, admin_conn, channel, other_channel
):
    add_message(admin_conn, channel, "D17", "Quando vence o DAS esse mes?")
    add_message(admin_conn, other_channel, "D18", "Quando vence o DAS esse mes?")
    classify_pending(database, channel.tenant_id)
    classify_pending(database, other_channel.tenant_id)

    materialize_demands(database, channel.tenant_id)

    assert len(demands_of(admin_conn, channel.tenant_id)) == 1
    assert demands_of(admin_conn, other_channel.tenant_id) == []
