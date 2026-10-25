from uuid import UUID

import psycopg
import pytest

from tests.conftest import ChannelFixture


def make_contact(conn, tenant_id: UUID, phone: str = "5511999990101") -> UUID:
    return conn.execute(
        "INSERT INTO contacts (tenant_id, phone) VALUES (%s, %s) RETURNING id", (tenant_id, phone)
    ).fetchone()[0]


def make_demand(conn, tenant_id: UUID, contact_id=None, status="novo", **extra) -> UUID:
    closed = "now()" if status == "concluido" else "NULL"
    return conn.execute(
        "INSERT INTO demands "
        "(tenant_id, contact_id, sector, kind, urgency, status, title, closed_at) "
        f"VALUES (%s, %s, 'fiscal', 'tarefa', 'normal', %s, 'Teste', {closed}) RETURNING id",
        (tenant_id, contact_id, status),
    ).fetchone()[0]


def set_tenant(conn, tenant_id: UUID):
    conn.execute("SELECT set_config('app.tenant_id', %s, false)", (str(tenant_id),))


def test_contact_phone_is_unique_per_tenant_but_not_across_tenants(
    admin_conn, channel: ChannelFixture, other_channel: ChannelFixture
):
    make_contact(admin_conn, channel.tenant_id)
    make_contact(admin_conn, other_channel.tenant_id)

    with pytest.raises(psycopg.errors.UniqueViolation):
        make_contact(admin_conn, channel.tenant_id)


def test_contact_kind_is_restricted(admin_conn, channel: ChannelFixture):
    with pytest.raises(psycopg.errors.CheckViolation):
        admin_conn.execute(
            "INSERT INTO contacts (tenant_id, phone, kind) VALUES (%s, '5511', 'alienigena')",
            (channel.tenant_id,),
        )


def test_demand_cannot_point_to_a_contact_of_another_tenant(
    admin_conn, channel: ChannelFixture, other_channel: ChannelFixture
):
    foreign_contact = make_contact(admin_conn, other_channel.tenant_id)

    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        make_demand(admin_conn, channel.tenant_id, contact_id=foreign_contact)


def test_message_cannot_point_to_a_contact_of_another_tenant(
    admin_conn, channel: ChannelFixture, other_channel: ChannelFixture
):
    foreign_contact = make_contact(admin_conn, other_channel.tenant_id)

    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        admin_conn.execute(
            "INSERT INTO messages (tenant_id, channel_id, provider_message_id, direction, "
            "remote_jid, contact_phone, message_type, provider_timestamp, raw, contact_id) "
            "VALUES (%s, %s, 'FK1', 'in', 'x@s.whatsapp.net', '5511', 'conversation', now(), "
            "'{}'::jsonb, %s)",
            (channel.tenant_id, channel.channel_id, foreign_contact),
        )


def test_demand_status_and_closed_at_must_agree(admin_conn, channel: ChannelFixture):
    with pytest.raises(psycopg.errors.CheckViolation):
        admin_conn.execute(
            "INSERT INTO demands (tenant_id, sector, kind, urgency, status, title) "
            "VALUES (%s, 'fiscal', 'tarefa', 'normal', 'concluido', 'sem closed_at')",
            (channel.tenant_id,),
        )
    with pytest.raises(psycopg.errors.CheckViolation):
        admin_conn.execute(
            "INSERT INTO demands (tenant_id, sector, kind, urgency, status, title) "
            "VALUES (%s, 'fiscal', 'tarefa', 'normal', 'inventado', 'status invalido')",
            (channel.tenant_id,),
        )


def test_app_role_only_sees_and_changes_its_own_tenants_demands(
    admin_conn, app_conn, channel: ChannelFixture, other_channel: ChannelFixture
):
    mine = make_demand(admin_conn, channel.tenant_id)
    theirs = make_demand(admin_conn, other_channel.tenant_id)
    set_tenant(app_conn, channel.tenant_id)

    visible = {row[0] for row in app_conn.execute("SELECT id FROM demands").fetchall()}
    assert visible == {mine}

    updated = app_conn.execute(
        "UPDATE demands SET status = 'em_andamento' WHERE id = %s", (theirs,)
    ).rowcount
    assert updated == 0
    assert app_conn.execute("SELECT count(*) FROM contacts").fetchone()[0] == 0


def test_app_role_can_update_but_never_delete_demands(
    admin_conn, app_conn, channel: ChannelFixture
):
    demand = make_demand(admin_conn, channel.tenant_id)
    set_tenant(app_conn, channel.tenant_id)

    app_conn.execute("UPDATE demands SET title = 'novo titulo' WHERE id = %s", (demand,))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app_conn.execute("DELETE FROM demands WHERE id = %s", (demand,))


def test_subtasks_belong_to_a_demand_of_the_same_tenant(
    admin_conn, channel: ChannelFixture, other_channel: ChannelFixture
):
    demand = make_demand(admin_conn, channel.tenant_id)

    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        admin_conn.execute(
            "INSERT INTO subtasks (tenant_id, demand_id, title) VALUES (%s, %s, 'x')",
            (other_channel.tenant_id, demand),
        )


def test_a_message_links_to_at_most_one_demand(admin_conn, channel: ChannelFixture):
    from tests.test_classification_store import add_message

    message = add_message(admin_conn, channel, "DM1", "texto")
    first = make_demand(admin_conn, channel.tenant_id)
    second = make_demand(admin_conn, channel.tenant_id)
    insert = "INSERT INTO demand_messages (tenant_id, demand_id, message_id) VALUES (%s, %s, %s)"
    admin_conn.execute(insert, (channel.tenant_id, first, message))

    with pytest.raises(psycopg.errors.UniqueViolation):
        admin_conn.execute(insert, (channel.tenant_id, second, message))


def test_user_email_is_unique_per_tenant_ignoring_case(admin_conn, channel: ChannelFixture):
    insert = (
        "INSERT INTO users (tenant_id, email, name, role, password_hash) "
        "VALUES (%s, %s, 'Fulano', 'socio', 'x')"
    )
    admin_conn.execute(insert, (channel.tenant_id, "Dono@Exemplo.com"))

    with pytest.raises(psycopg.errors.UniqueViolation):
        admin_conn.execute(insert, (channel.tenant_id, "dono@exemplo.com"))


def test_user_role_is_restricted(admin_conn, channel: ChannelFixture):
    with pytest.raises(psycopg.errors.CheckViolation):
        admin_conn.execute(
            "INSERT INTO users (tenant_id, email, name, role, password_hash) "
            "VALUES (%s, 'a@b.com', 'A', 'superadmin', 'x')",
            (channel.tenant_id,),
        )


def test_app_role_cannot_read_password_hashes(admin_conn, app_conn, channel: ChannelFixture):
    admin_conn.execute(
        "INSERT INTO users (tenant_id, email, name, role, password_hash) "
        "VALUES (%s, 'h@exemplo.com', 'H', 'socio', 'hash-secreto')",
        (channel.tenant_id,),
    )
    set_tenant(app_conn, channel.tenant_id)

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        app_conn.execute("SELECT password_hash FROM users")
    assert app_conn.execute("SELECT count(*) FROM users").fetchone()[0] == 1
    assert app_conn.execute("SELECT email, name, role FROM users").fetchone()[0] == "h@exemplo.com"
