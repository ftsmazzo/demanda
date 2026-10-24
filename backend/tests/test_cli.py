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


def test_stats_reports_counts_and_latency_per_channel(
    admin_url, admin_conn, channel, monkeypatch, capsys
):
    from datetime import UTC, datetime, timedelta

    monkeypatch.setenv("DATABASE_URL", admin_url)
    sent_at = datetime.now(UTC) - timedelta(seconds=2)
    for message_id, direction in (("S1", "in"), ("S2", "out")):
        admin_conn.execute(
            "INSERT INTO messages (tenant_id, channel_id, provider_message_id, direction, "
            "remote_jid, contact_phone, message_type, provider_timestamp, raw) "
            "VALUES (%s, %s, %s, %s, 'x@s.whatsapp.net', '5511', 'conversation', %s, '{}')",
            (channel.tenant_id, channel.channel_id, message_id, direction, sent_at),
        )

    code = cli.main(["stats"])

    out = capsys.readouterr().out
    assert code == 0
    line = next(row for row in out.splitlines() if str(channel.channel_id) in row)
    assert "total=2" in line
    assert "in=1" in line
    assert "out=1" in line
    assert "latencia_media_s=" in line
