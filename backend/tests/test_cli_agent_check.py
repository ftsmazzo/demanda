from datetime import UTC, datetime, timedelta

from app import cli
from tests.agent_helpers import add_appointment, add_demand, add_recipient


def check(monkeypatch, admin_url, capsys, slug, **env):
    for key in (
        "WORKER_INTERVAL_SECONDS",
        "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
        "CASE_LLM",
        "AGENT_INSTANCE",
        "AGENT_SEND",
        "AGENT_WEBHOOK_SECRET",
        "EVOLUTION_URL",
        "EVOLUTION_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("DATABASE_URL", admin_url)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    capsys.readouterr()
    code = cli.main(["agent-check", "--tenant-slug", slug])
    return code, capsys.readouterr().out


def slug_of(admin_conn, tenant_id):
    return admin_conn.execute("SELECT slug FROM tenants WHERE id = %s", (tenant_id,)).fetchone()[0]


def test_it_reports_what_is_off_and_never_prints_secrets(
    admin_url, admin_conn, tenant_id, monkeypatch, capsys
):
    code, out = check(monkeypatch, admin_url, capsys, slug_of(admin_conn, tenant_id))

    assert code == 0
    assert "worker: desligado" in out
    assert "linguagem natural desligada" in out
    assert "agente: desligado" in out and "AGENT_INSTANCE" in out
    assert "destinatarios ativos: 0" in out


def test_it_describes_a_working_setup(admin_url, admin_conn, tenant_id, monkeypatch, capsys):
    add_recipient(admin_conn, tenant_id, "5511999990001")

    code, out = check(
        monkeypatch,
        admin_url,
        capsys,
        slug_of(admin_conn, tenant_id),
        WORKER_INTERVAL_SECONDS="30",
        OPENROUTER_API_KEY="sk-or-segredo-de-teste",
        EVOLUTION_URL="https://evo.example.com",
        EVOLUTION_API_KEY="chave-secreta-evolution",
        AGENT_INSTANCE="secretaria",
        AGENT_SEND="1",
        AGENT_WEBHOOK_SECRET="segredo-do-webhook",
    )

    assert code == 0
    assert "worker: ligado a cada 30s" in out
    assert "linguagem natural via OpenRouter" in out
    assert "IA de caso: ligada" in out
    assert "ENVIO REAL" in out
    assert "segredo do webhook: definido" in out
    assert "destinatarios ativos: 1" in out
    for secret in ("sk-or-segredo-de-teste", "chave-secreta-evolution", "segredo-do-webhook"):
        assert secret not in out


def test_it_says_rehearsal_when_sending_is_not_enabled(
    admin_url, admin_conn, tenant_id, monkeypatch, capsys
):
    _, out = check(
        monkeypatch,
        admin_url,
        capsys,
        slug_of(admin_conn, tenant_id),
        EVOLUTION_URL="https://evo.example.com",
        EVOLUTION_API_KEY="k",
        AGENT_INSTANCE="secretaria",
        AGENT_SEND="0",
    )

    assert "ENSAIO" in out and "nada e enviado" in out


def test_it_lists_proposed_appointments_and_whether_each_was_announced(
    admin_url, admin_conn, tenant_id, monkeypatch, capsys
):
    recipient = add_recipient(admin_conn, tenant_id, "5511999990002")
    now = datetime.now(UTC)
    demand = add_demand(admin_conn, tenant_id, title="Base", now=now)
    told = add_appointment(
        admin_conn,
        tenant_id,
        demand,
        starts_at=now + timedelta(days=2),
        created_at=now - timedelta(hours=2),
        title="Ja avisada xyzcheck1",
    )
    add_appointment(
        admin_conn,
        tenant_id,
        demand,
        starts_at=now + timedelta(days=3),
        created_at=now - timedelta(hours=1),
        title="Sem aviso xyzcheck2",
    )
    admin_conn.execute(
        "INSERT INTO agent_notifications (tenant_id, recipient_id, kind, dedupe_key, body, status) "
        "VALUES (%s, %s, 'appointment', %s, 'x', 'dry_run')",
        (tenant_id, recipient, str(told)),
    )

    _, out = check(monkeypatch, admin_url, capsys, slug_of(admin_conn, tenant_id))

    line_told = next(line for line in out.splitlines() if "xyzcheck1" in line)
    line_missing = next(line for line in out.splitlines() if "xyzcheck2" in line)
    assert "avisado" in line_told and "NAO" not in line_told
    assert "NAO avisado" in line_missing


def test_an_unknown_tenant_is_an_error(admin_url, monkeypatch, capsys):
    code, _ = check(monkeypatch, admin_url, capsys, "nao-existe")

    assert code == 1


def test_check_shows_how_much_of_the_daily_budget_is_used(
    admin_url, admin_conn, tenant_id, monkeypatch, capsys
):
    recipient = add_recipient(admin_conn, tenant_id, "5511999990003")
    for number in range(3):
        admin_conn.execute(
            "INSERT INTO agent_notifications (tenant_id, recipient_id, kind, dedupe_key, body, "
            "status) VALUES (%s, %s, 'stuck', %s, 'x', 'sent')",
            (tenant_id, recipient, f"k{number}"),
        )

    _, out = check(monkeypatch, admin_url, capsys, slug_of(admin_conn, tenant_id))

    assert "avisos das ultimas 24 h: 3 de 20" in out


def test_retry_puts_recent_skipped_alerts_back_in_the_queue(
    admin_url, admin_conn, tenant_id, monkeypatch, capsys
):
    recipient = add_recipient(admin_conn, tenant_id, "5511999990004")
    admin_conn.execute(
        "INSERT INTO agent_notifications (tenant_id, recipient_id, kind, dedupe_key, body, status) "
        "VALUES (%s, %s, 'appointment', 'a', 'Texto do aviso', 'skipped'), "
        "(%s, %s, 'stuck', 'b', '', 'skipped')",
        (tenant_id, recipient, tenant_id, recipient),
    )
    monkeypatch.setenv("DATABASE_URL", admin_url)

    code = cli.main(["agent-retry", "--tenant-slug", slug_of(admin_conn, tenant_id)])

    states = dict(
        admin_conn.execute(
            "SELECT dedupe_key, status FROM agent_notifications WHERE tenant_id = %s", (tenant_id,)
        ).fetchall()
    )
    assert code == 0
    assert states == {"a": "pending", "b": "skipped"}  # o vazio nao tem o que enviar
    assert "1 aviso" in capsys.readouterr().out
