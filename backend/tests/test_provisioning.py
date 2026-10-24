import hashlib
from uuid import uuid4

from app.provisioning import create_channel, create_tenant


def test_channel_secret_is_returned_once_and_stored_only_as_hash(admin_conn, tenant_id):
    channel_id, secret = create_channel(
        admin_conn, tenant_id=tenant_id, name="DP", instance_name="dp"
    )

    stored = admin_conn.execute(
        "SELECT webhook_secret_hash FROM channels WHERE id = %s", (channel_id,)
    ).fetchone()[0]

    assert len(secret) >= 32
    assert stored == hashlib.sha256(secret.encode()).hexdigest()
    assert secret not in stored


def test_create_tenant_returns_its_id(admin_conn):
    tenant_id = create_tenant(admin_conn, slug=f"prov-{uuid4().hex[:8]}", name="Provisioning")

    row = admin_conn.execute("SELECT slug FROM tenants WHERE id = %s", (tenant_id,)).fetchone()

    assert row[0].startswith("prov-")


def test_runtime_role_is_unprivileged_and_cannot_escape_the_app_role(admin_url, admin_conn):
    import psycopg
    import pytest

    from app.provisioning import create_runtime_role

    create_runtime_role(admin_conn, password="pw-only-for-tests")
    create_runtime_role(admin_conn, password="pw-only-for-tests-2")  # idempotente

    flags = admin_conn.execute(
        "SELECT rolsuper, rolbypassrls, rolinherit, rolcanlogin FROM pg_roles "
        "WHERE rolname = 'demanda_runtime'"
    ).fetchone()
    assert flags == (False, False, False, True)

    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute("SET SESSION AUTHORIZATION demanda_runtime")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT count(*) FROM messages")
        conn.execute("SET ROLE demanda_app")
        assert conn.execute("SELECT count(*) FROM messages").fetchone()[0] == 0
        conn.execute("RESET ROLE")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT count(*) FROM messages")
