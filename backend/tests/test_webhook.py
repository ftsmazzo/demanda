from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import ChannelFixture
from tests.factories import upsert_item, upsert_payload


def count_messages(admin_conn, channel: ChannelFixture) -> int:
    return admin_conn.execute(
        "SELECT count(*) FROM messages WHERE channel_id = %s", (channel.channel_id,)
    ).fetchone()[0]


def post(client, channel: ChannelFixture, payload, headers=None):
    return client.post(
        channel.path, json=payload, headers=channel.headers if headers is None else headers
    )


def test_valid_message_is_stored_with_channel_tenant(client, admin_conn, channel):
    payload = upsert_payload(upsert_item("W1", message={"conversation": "Boa tarde"}))

    response = post(client, channel, payload)

    assert response.status_code == 200
    assert response.json() == {"received": 1, "stored": 1, "duplicates": 0, "ignored": 0}
    row = admin_conn.execute(
        "SELECT tenant_id, direction, contact_phone, text, raw->'key'->>'id' "
        "FROM messages WHERE channel_id = %s",
        (channel.channel_id,),
    ).fetchone()
    assert row == (channel.tenant_id, "in", "5511999990101", "Boa tarde", "W1")


def test_redelivery_is_idempotent(client, admin_conn, channel):
    payload = upsert_payload(upsert_item("W2"))

    first = post(client, channel, payload)
    second = post(client, channel, payload)

    assert first.json()["stored"] == 1
    assert second.status_code == 200
    assert second.json() == {"received": 1, "stored": 0, "duplicates": 1, "ignored": 0}
    assert count_messages(admin_conn, channel) == 1


def test_same_provider_id_in_different_channels_is_stored_twice(
    client, admin_conn, channel, other_channel
):
    payload = upsert_payload(upsert_item("SAME"))

    post(client, channel, payload)
    post(client, other_channel, payload)

    assert count_messages(admin_conn, channel) == 1
    assert count_messages(admin_conn, other_channel) == 1


def test_batch_payload_stores_every_message(client, admin_conn, channel):
    payload = upsert_payload(upsert_item("B1"), upsert_item("B2"), upsert_item("B3"))

    response = post(client, channel, payload)

    assert response.json()["stored"] == 3
    assert count_messages(admin_conn, channel) == 3


def test_outgoing_messages_are_stored_too(client, admin_conn, channel):
    post(client, channel, upsert_payload(upsert_item("O1", from_me=True)))

    row = admin_conn.execute(
        "SELECT direction FROM messages WHERE channel_id = %s", (channel.channel_id,)
    ).fetchone()
    assert row == ("out",)


def test_groups_are_ignored_unless_channel_listens_to_them(client, admin_conn, channel):
    payload = upsert_payload(upsert_item("G1", jid="120363000000000000@g.us"))

    response = post(client, channel, payload)

    assert response.json() == {"received": 0, "stored": 0, "duplicates": 0, "ignored": 1}
    assert count_messages(admin_conn, channel) == 0


def test_other_events_are_acknowledged_and_ignored(client, admin_conn, channel):
    payload = upsert_payload(upsert_item("U1"), event="connection.update")

    response = post(client, channel, payload)

    assert response.status_code == 200
    assert response.json() == {"status": "ignored", "event": "connection.update"}
    assert count_messages(admin_conn, channel) == 0


def test_event_name_variants_are_accepted(client, admin_conn, channel):
    payload = upsert_payload(upsert_item("E1"), event="MESSAGES_UPSERT")

    assert post(client, channel, payload).json()["stored"] == 1


def test_wrong_secret_is_rejected_and_nothing_is_stored(client, admin_conn, channel):
    response = post(client, channel, upsert_payload(upsert_item("X1")), {"X-Webhook-Secret": "no"})

    assert response.status_code == 401
    assert count_messages(admin_conn, channel) == 0


def test_missing_secret_is_rejected(client, channel):
    response = client.post(channel.path, json=upsert_payload(upsert_item("X2")))

    assert response.status_code == 401


def test_secret_of_another_channel_is_rejected(client, channel, other_channel):
    response = post(client, channel, upsert_payload(upsert_item("X3")), other_channel.headers)

    assert response.status_code == 401


def test_unknown_channel_gets_the_same_401_as_a_bad_secret(client, channel):
    response = client.post(
        "/webhooks/evolution/00000000-0000-0000-0000-000000000000",
        json=upsert_payload(upsert_item("X4")),
        headers=channel.headers,
    )

    assert response.status_code == 401


def test_inactive_channel_is_rejected(client, admin_conn, channel):
    admin_conn.execute("UPDATE channels SET active = false WHERE id = %s", (channel.channel_id,))

    assert post(client, channel, upsert_payload(upsert_item("X5"))).status_code == 401


def test_invalid_channel_id_is_422(client, channel):
    response = client.post("/webhooks/evolution/not-a-uuid", json={}, headers=channel.headers)

    assert response.status_code == 422


def test_webhook_without_database_is_503():
    with TestClient(create_app(database_url=None)) as no_db_client:
        response = no_db_client.post(
            "/webhooks/evolution/00000000-0000-0000-0000-000000000000",
            json={},
            headers={"X-Webhook-Secret": "x"},
        )

    assert response.status_code == 503


def test_readiness_reports_database_state(client):
    assert client.get("/health/ready").json() == {"status": "ok"}


def test_readiness_without_database_is_503():
    with TestClient(create_app(database_url=None)) as no_db_client:
        assert no_db_client.get("/health/ready").status_code == 503
        assert no_db_client.get("/health").status_code == 200


def test_nul_character_does_not_poison_the_batch(client, admin_conn, channel):
    payload = upsert_payload(
        upsert_item("N1", message={"conversation": "ol\x00a"}), upsert_item("N2")
    )

    response = post(client, channel, payload)

    assert response.status_code == 200
    assert response.json()["stored"] == 2
    text = admin_conn.execute(
        "SELECT text FROM messages WHERE channel_id = %s AND provider_message_id = 'N1'",
        (channel.channel_id,),
    ).fetchone()[0]
    assert text == "ola"


def test_oversized_body_is_rejected_with_413(admin_url, channel):
    payload = upsert_payload(upsert_item("BIG", message={"conversation": "x" * 5000}))

    with TestClient(create_app(database_url=admin_url, max_body_bytes=1000)) as small_client:
        response = post(small_client, channel, payload)

    assert response.status_code == 413


def test_failed_authentication_is_logged_without_the_secret(client, channel, caplog):
    with caplog.at_level("WARNING"):
        post(client, channel, upsert_payload(upsert_item("L1")), {"X-Webhook-Secret": "guess"})

    assert str(channel.channel_id) in caplog.text
    assert "guess" not in caplog.text


def test_ignored_event_name_is_not_echoed_in_full(client, channel):
    response = post(client, channel, upsert_payload(upsert_item("V1"), event="x" * 500))

    assert response.status_code == 200
    assert len(response.json()["event"]) <= 64


def test_pool_exhaustion_returns_503(client, channel, monkeypatch):
    from psycopg_pool import PoolTimeout

    def boom(_channel_id):
        raise PoolTimeout("no connections")

    monkeypatch.setattr(client.app.state.db, "auth_channel", boom)

    response = post(client, channel, upsert_payload(upsert_item("T1")))

    assert response.status_code == 503


def test_interactive_docs_are_disabled(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_startup_provisions_runtime_role_when_password_is_given(admin_url, admin_conn):
    admin_conn.execute("DROP OWNED BY demanda_runtime CASCADE") if admin_conn.execute(
        "SELECT 1 FROM pg_roles WHERE rolname = 'demanda_runtime'"
    ).fetchone() else None
    admin_conn.execute("DROP ROLE IF EXISTS demanda_runtime")

    app = create_app(admin_url, auto_migrate=True, runtime_password="pw-only-for-tests")
    with TestClient(app):
        pass

    row = admin_conn.execute(
        "SELECT rolcanlogin FROM pg_roles WHERE rolname = 'demanda_runtime'"
    ).fetchone()
    assert row == (True,)
