from uuid import uuid4

import psycopg
import pytest
from psycopg import conninfo

from app.migrate import apply_migrations
from app.provisioning import create_channel, create_tenant


@pytest.fixture
def legacy_db_url(admin_url):
    """Banco novo e vazio, para testar migrations contra dados que ja existiam."""
    name = f"legacy_{uuid4().hex[:8]}"
    params = conninfo.conninfo_to_dict(admin_url)
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    url = conninfo.make_conninfo(**{**params, "dbname": name})
    yield url
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE "{name}" WITH (FORCE)')


def insert_message(conn, tenant_id, channel_id, message_id, direction, phone, push_name, ts):
    conn.execute(
        "INSERT INTO messages (tenant_id, channel_id, provider_message_id, direction, remote_jid, "
        "contact_phone, push_name, message_type, provider_timestamp, raw) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, 'conversation', %s, '{}'::jsonb)",
        (
            tenant_id,
            channel_id,
            message_id,
            direction,
            f"{phone}@s.whatsapp.net",
            phone,
            push_name,
            ts,
        ),
    )


def test_backfill_creates_one_contact_per_phone_and_links_every_message(legacy_db_url):
    applied = apply_migrations(legacy_db_url, up_to="0003_reclassify_no_llm")
    assert applied[-1] == "0003_reclassify_no_llm"

    with psycopg.connect(legacy_db_url, autocommit=True) as conn:
        tenant = create_tenant(conn, slug="legado", name="Legado")
        channel, _ = create_channel(conn, tenant_id=tenant, name="Principal", instance_name="x")
        insert_message(
            conn, tenant, channel, "L1", "in", "5511111111111", "Nome Antigo", "2026-10-01T10:00Z"
        )
        insert_message(
            conn, tenant, channel, "L2", "in", "5511111111111", "Nome Novo", "2026-10-02T10:00Z"
        )
        insert_message(
            conn, tenant, channel, "L3", "out", "5522222222222", "Escritorio", "2026-10-02T11:00Z"
        )

    assert apply_migrations(legacy_db_url) == ["0004_core"]

    with psycopg.connect(legacy_db_url, autocommit=True) as conn:
        contacts = conn.execute("SELECT phone, name FROM contacts ORDER BY phone").fetchall()
        unlinked = conn.execute(
            "SELECT count(*) FROM messages WHERE contact_id IS NULL"
        ).fetchone()[0]
        mismatched = conn.execute(
            "SELECT count(*) FROM messages m JOIN contacts c ON c.id = m.contact_id "
            "WHERE c.phone <> m.contact_phone OR c.tenant_id <> m.tenant_id"
        ).fetchone()[0]

    assert contacts == [("5511111111111", "Nome Novo"), ("5522222222222", None)]
    assert unlinked == 0
    assert mismatched == 0


def test_migrations_apply_cleanly_on_an_empty_database(legacy_db_url):
    applied = apply_migrations(legacy_db_url)

    assert applied[0] == "0001_init"
    assert applied[-1] == "0004_core"
