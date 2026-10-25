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


def test_classify_pending_command_classifies_without_llm(
    admin_url, admin_conn, channel, monkeypatch, capsys
):
    from tests.test_classification_store import add_message

    monkeypatch.setenv("DATABASE_URL", admin_url)
    monkeypatch.setenv("APP_DATABASE_URL", admin_url)
    message = add_message(admin_conn, channel, "C1", "Quando vence o DAS esse mes?")

    code = cli.main(["classify-pending", "--no-llm"])

    out = capsys.readouterr().out
    assert code == 0
    assert "classified=1" in out
    row = admin_conn.execute(
        "SELECT sector FROM message_classifications WHERE message_id = %s", (message,)
    ).fetchone()
    assert row == ("fiscal",)


def test_classify_pending_warns_when_the_api_key_is_missing(
    admin_url, admin_conn, channel, monkeypatch, capsys
):
    from tests.test_classification_store import add_message

    monkeypatch.setenv("DATABASE_URL", admin_url)
    monkeypatch.setenv("APP_DATABASE_URL", admin_url)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    add_message(admin_conn, channel, "C2", "Pode me ajudar com uma coisa aqui?")

    code = cli.main(["classify-pending"])

    assert code == 0
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().out


def test_classify_pending_refuses_to_run_without_the_restricted_runtime_url(
    admin_url, monkeypatch, capsys
):
    monkeypatch.setenv("DATABASE_URL", admin_url)
    monkeypatch.delenv("APP_DATABASE_URL", raising=False)

    code = cli.main(["classify-pending", "--no-llm"])

    assert code == 2
    assert "APP_DATABASE_URL" in capsys.readouterr().err


@pytest.mark.parametrize("limit", ["0", "-5", "100000"])
def test_classify_pending_limit_must_be_between_1_and_1000(limit):
    with pytest.raises(SystemExit):
        cli.main(["classify-pending", "--limit", limit])


def test_review_lists_classified_messages_and_can_filter_the_ones_needing_review(
    admin_url, admin_conn, channel, monkeypatch, capsys
):
    from app.classification.store import classify_pending
    from app.db import Database
    from tests.test_classification_store import add_message

    monkeypatch.setenv("DATABASE_URL", admin_url)
    add_message(admin_conn, channel, "R1", "Quando vence o DAS esse mes?", minutes=200000)
    add_message(admin_conn, channel, "R2", "Pode me ajudar com uma coisa aqui?", minutes=200001)
    db = Database(admin_url)
    db.open()
    try:
        classify_pending(db, channel.tenant_id)
    finally:
        db.close()

    assert cli.main(["review"]) == 0
    everything = capsys.readouterr().out
    assert "Quando vence o DAS" in everything
    assert "Pode me ajudar" in everything
    assert "fiscal/duvida/normal" in everything

    assert cli.main(["review", "--needs-review"]) == 0
    only_review = capsys.readouterr().out
    assert "Pode me ajudar" in only_review
    assert "Quando vence o DAS" not in only_review
    assert "no_llm" in only_review


def test_review_hides_most_of_the_phone_number(admin_url, admin_conn, channel, monkeypatch, capsys):
    from app.classification.store import classify_pending
    from app.db import Database
    from tests.test_classification_store import add_message

    monkeypatch.setenv("DATABASE_URL", admin_url)
    add_message(
        admin_conn,
        channel,
        "R3",
        "Quando vence o DAS esse mes?",
        phone="5511987654321",
        minutes=300000,
    )
    db = Database(admin_url)
    db.open()
    try:
        classify_pending(db, channel.tenant_id)
    finally:
        db.close()

    cli.main(["review"])

    out = capsys.readouterr().out
    assert "987654321" not in out
    assert "4321" in out


def test_review_shows_only_the_latest_classification_of_each_message(
    admin_url, admin_conn, channel, monkeypatch, capsys
):
    from app.classification.store import classify_pending
    from app.db import Database
    from tests.test_classification_service import FakeLLM, llm_output
    from tests.test_classification_store import add_message

    monkeypatch.setenv("DATABASE_URL", admin_url)
    add_message(admin_conn, channel, "R9", "Pode me ajudar com o caso xyzunico?", minutes=400000)
    db = Database(admin_url)
    db.open()
    try:
        classify_pending(db, channel.tenant_id)
        classify_pending(db, channel.tenant_id, llm=FakeLLM(llm_output(sector="dp", kind="duvida")))
    finally:
        db.close()

    cli.main(["review", "--limit", "5"])

    lines = [row for row in capsys.readouterr().out.splitlines() if "xyzunico" in row]
    assert len(lines) == 1
    assert "dp/duvida" in lines[0]
