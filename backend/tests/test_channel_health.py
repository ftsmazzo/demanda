import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.channel_health import check_channels
from app.provisioning import create_channel
from tests.conftest import ChannelFixture


@pytest.fixture
def instance():
    """Nome de instancia proprio: o banco de teste e compartilhado entre os testes."""
    return f"inst-{uuid.uuid4().hex[:10]}"


@pytest.fixture
def channel(admin_conn, tenant_id, instance):
    channel_id, secret = create_channel(
        admin_conn, tenant_id=tenant_id, name="Monitor", instance_name=instance
    )
    return ChannelFixture(tenant_id, channel_id, secret)


class FakeEvolution:
    def __init__(self, states, pages=None):
        self.states = states  # instance_name -> estado
        self.pages = pages or {}  # instance_name -> lista de paginas (cada uma, lista de registros)
        self.calls = []

    def connection_state(self, instance):
        return self.states.get(instance, "unknown")

    def find_messages(self, instance, *, since, until, page=1, offset=50):
        self.calls.append((instance, since, until, page))
        pages = self.pages.get(instance, [[]])
        records = pages[page - 1] if page <= len(pages) else []
        return records, len(pages)


def record(message_id, text, phone="5511988880001"):
    return {
        "key": {"id": message_id, "remoteJid": f"{phone}@s.whatsapp.net", "fromMe": False},
        "pushName": "Cliente Perdido",
        "messageType": "conversation",
        "message": {"conversation": text},
        "messageTimestamp": int(datetime.now(UTC).timestamp()),
    }


def health_of(admin_conn, channel):
    return admin_conn.execute(
        "SELECT health_state, health_changed_at, last_reconciled_at FROM channels WHERE id = %s",
        (channel.channel_id,),
    ).fetchone()


def texts(admin_conn, channel):
    rows = admin_conn.execute(
        "SELECT text FROM messages WHERE channel_id = %s", (channel.channel_id,)
    ).fetchall()
    return {row[0] for row in rows}


def test_the_state_is_recorded_and_the_change_time_only_moves_on_a_change(
    database, admin_conn, channel, instance
):
    evolution = FakeEvolution({instance: "close"})
    check_channels(database, evolution)
    first = health_of(admin_conn, channel)

    check_channels(database, evolution)
    second = health_of(admin_conn, channel)
    evolution.states[instance] = "open"
    check_channels(database, evolution)
    third = health_of(admin_conn, channel)

    assert (first[0], second[0], third[0]) == ("close", "close", "open")
    assert first[1] == second[1]
    assert third[1] > second[1]


def test_a_closed_instance_is_not_reconciled(database, admin_conn, channel, instance):
    evolution = FakeEvolution({instance: "close"})

    check_channels(database, evolution)

    assert [call for call in evolution.calls if call[0] == instance] == []
    assert health_of(admin_conn, channel)[2] is None


def test_an_open_instance_pulls_the_messages_the_webhook_missed(
    database, admin_conn, channel, instance
):
    pages = {instance: [[record("PERD1", "Preciso da guia xyzperdida")]]}
    evolution = FakeEvolution({instance: "open"}, pages)

    summary = check_channels(database, evolution)

    assert "Preciso da guia xyzperdida" in texts(admin_conn, channel)
    assert summary["reconciled_stored"] >= 1
    assert health_of(admin_conn, channel)[2] is not None
    contact = admin_conn.execute(
        "SELECT id FROM contacts WHERE tenant_id = %s AND phone = '5511988880001'",
        (channel.tenant_id,),
    ).fetchone()
    assert contact is not None


def test_reconciling_twice_does_not_duplicate(database, admin_conn, channel, instance):
    pages = {instance: [[record("PERD2", "xyzunica")]]}
    evolution = FakeEvolution({instance: "open"}, pages)

    check_channels(database, evolution)
    check_channels(database, evolution)

    count = admin_conn.execute(
        "SELECT count(*) FROM messages WHERE channel_id = %s AND provider_message_id = 'PERD2'",
        (channel.channel_id,),
    ).fetchone()[0]
    assert count == 1


def test_it_walks_further_pages_only_while_they_bring_new_messages(
    database, admin_conn, channel, instance
):
    pages = {
        instance: [
            [record("P1", "um xyzpag")],
            [record("P2", "dois xyzpag")],
            [record("P3", "tres xyzpag")],
        ]
    }
    evolution = FakeEvolution({instance: "open"}, pages)

    check_channels(database, evolution)

    asked = [call[3] for call in evolution.calls if call[0] == instance]
    assert asked == [1, 2, 3]
    assert {"um xyzpag", "dois xyzpag", "tres xyzpag"} <= texts(admin_conn, channel)

    evolution.calls.clear()
    check_channels(database, evolution)
    assert [call[3] for call in evolution.calls if call[0] == instance] == [1]


def test_the_window_starts_a_little_before_the_last_reconciliation(
    database, admin_conn, channel, instance
):
    evolution = FakeEvolution({instance: "open"})
    check_channels(database, evolution)
    last = health_of(admin_conn, channel)[2]
    evolution.calls.clear()

    check_channels(database, evolution)

    since = next(call[1] for call in evolution.calls if call[0] == instance)
    assert last - timedelta(minutes=30) <= since <= last - timedelta(minutes=5)


def test_an_unreachable_evolution_does_not_break_the_cycle(database, admin_conn, channel, instance):
    evolution = FakeEvolution({instance: "unreachable"})

    summary = check_channels(database, evolution)

    assert health_of(admin_conn, channel)[0] == "unreachable"
    assert summary["checked"] >= 1


def test_each_channel_is_asked_by_its_own_instance_name(database, channel, other_channel, instance):
    evolution = FakeEvolution({instance: "open", "outro": "open"})

    check_channels(database, evolution)

    assert {call[0] for call in evolution.calls} >= {instance, "outro"}
