import hashlib

import pytest

from app import cli


def test_create_channel_prints_secret_that_matches_stored_hash(
    admin_url, admin_conn, tenant_id, monkeypatch, capsys
):
    monkeypatch.setenv("DATABASE_URL", admin_url)
    slug = admin_conn.execute("SELECT slug FROM tenants WHERE id = %s", (tenant_id,)).fetchone()[0]

    code = cli.main(["create-channel", "--tenant-slug", slug, "--name", "CLI", "--instance", "cli"])

    out = capsys.readouterr().out
    assert code == 0
    secret = out.split("nao sera exibido de novo): ")[1].strip()
    stored = admin_conn.execute(
        "SELECT webhook_secret_hash FROM channels WHERE instance_name = 'cli' AND tenant_id = %s",
        (tenant_id,),
    ).fetchone()[0]
    assert stored == hashlib.sha256(secret.encode()).hexdigest()


def test_create_channel_for_unknown_tenant_fails(admin_url, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", admin_url)

    code = cli.main(
        ["create-channel", "--tenant-slug", "nao-existe", "--name", "x", "--instance", "x"]
    )

    assert code == 1
    assert "nao encontrado" in capsys.readouterr().err


def test_missing_database_url_is_an_error(monkeypatch, capsys):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert cli.main(["create-tenant", "--slug", "a", "--name", "A"]) == 2


def test_unknown_command_exits_with_usage_error():
    with pytest.raises(SystemExit):
        cli.main(["nope"])
