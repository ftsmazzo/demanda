from datetime import UTC, datetime
from uuid import UUID

import psycopg
import pytest

from app.migrate import apply_migrations
from tests.conftest import ChannelFixture

INSERT_MESSAGE = """
    INSERT INTO messages (tenant_id, channel_id, provider_message_id, direction, remote_jid,
                          contact_phone, message_type, provider_timestamp, raw)
    VALUES (%s, %s, %s, 'in', '5511999990101@s.whatsapp.net', '5511999990101',
            'conversation', %s, '{}'::jsonb)
"""


def add_message(conn, tenant_id: UUID, channel_id: UUID, message_id: str = "M1"):
    conn.execute(INSERT_MESSAGE, (tenant_id, channel_id, message_id, datetime.now(UTC)))


def set_tenant(conn, tenant_id: UUID):
    conn.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))


def test_migrations_are_idempotent(admin_url):
    assert apply_migrations(admin_url) == []


def test_message_id_is_unique_per_channel(admin_conn, channel: ChannelFixture):
    add_message(admin_conn, channel.tenant_id, channel.channel_id, "DUP")

    with pytest.raises(psycopg.errors.UniqueViolation):
        add_message(admin_conn, channel.tenant_id, channel.channel_id, "DUP")


def test_message_cannot_reference_channel_of_another_tenant(
    admin_conn, channel: ChannelFixture, other_channel: ChannelFixture
):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        add_message(admin_conn, other_channel.tenant_id, channel.channel_id)


def test_app_role_sees_nothing_without_tenant_context(
    admin_conn, app_conn, channel: ChannelFixture
):
    add_message(admin_conn, channel.tenant_id, channel.channel_id)

    assert app_conn.execute("SELECT count(*) FROM messages").fetchone()[0] == 0
    assert app_conn.execute("SELECT count(*) FROM channels").fetchone()[0] == 0
    assert app_conn.execute("SELECT count(*) FROM tenants").fetchone()[0] == 0


def test_app_role_only_sees_rows_of_the_current_tenant(
    admin_conn, app_conn, channel: ChannelFixture, other_channel: ChannelFixture
):
    add_message(admin_conn, channel.tenant_id, channel.channel_id, "MINE")
    add_message(admin_conn, other_channel.tenant_id, other_channel.channel_id, "THEIRS")

    set_tenant(app_conn, channel.tenant_id)

    rows = app_conn.execute("SELECT provider_message_id FROM messages").fetchall()
    assert rows == [("MINE",)]
    assert app_conn.execute("SELECT count(*) FROM channels").fetchone()[0] == 1
    assert app_conn.execute("SELECT count(*) FROM tenants").fetchone()[0] == 1


def test_app_role_cannot_insert_for_another_tenant(
    app_conn, channel: ChannelFixture, other_channel: ChannelFixture
):
    set_tenant(app_conn, channel.tenant_id)

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        add_message(app_conn, other_channel.tenant_id, other_channel.channel_id)


def test_app_role_cannot_update_or_delete_messages(admin_conn, app_conn, channel: ChannelFixture):
    add_message(admin_conn, channel.tenant_id, channel.channel_id)
    set_tenant(app_conn, channel.tenant_id)

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app_conn.execute("UPDATE messages SET text = 'x'")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app_conn.execute("DELETE FROM messages")


def test_auth_channel_is_the_only_cross_tenant_lookup(app_conn, channel: ChannelFixture):
    row = app_conn.execute("SELECT * FROM auth_channel(%s)", (channel.channel_id,)).fetchone()

    assert row is not None
    assert row[0] == channel.tenant_id


def test_auth_channel_ignores_inactive_channels(admin_conn, app_conn, channel: ChannelFixture):
    admin_conn.execute("UPDATE channels SET active = false WHERE id = %s", (channel.channel_id,))

    assert (
        app_conn.execute("SELECT * FROM auth_channel(%s)", (channel.channel_id,)).fetchone() is None
    )
