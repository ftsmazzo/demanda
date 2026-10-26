import pytest

from app import cli
from tests.agent_helpers import add_recipient


def slug_of(admin_conn, tenant_id):
    return admin_conn.execute("SELECT slug FROM tenants WHERE id = %s", (tenant_id,)).fetchone()[0]


def run(monkeypatch, admin_url, *args):
    monkeypatch.setenv("DATABASE_URL", admin_url)
    return cli.main(list(args))


def test_add_recipient_stores_digits_only_and_lists_it(
    admin_url, admin_conn, tenant_id, monkeypatch, capsys
):
    slug = slug_of(admin_conn, tenant_id)

    code = run(
        monkeypatch,
        admin_url,
        "add-recipient",
        "--tenant-slug",
        slug,
        "--name",
        "Carlos Mendes",
        "--phone",
        "+55 (11) 99999-0101",
    )

    assert code == 0
    row = admin_conn.execute(
        "SELECT phone, name, active FROM agent_recipients WHERE tenant_id = %s", (tenant_id,)
    ).fetchone()
    assert row == ("5511999990101", "Carlos Mendes", True)
    capsys.readouterr()
    assert run(monkeypatch, admin_url, "recipients", "--tenant-slug", slug) == 0
    listing = capsys.readouterr().out
    assert "Carlos Mendes" in listing and "0101" in listing
    assert "99999" not in listing  # o numero aparece mascarado


def test_add_recipient_validates_the_phone_the_tenant_and_a_duplicate(
    admin_url, admin_conn, tenant_id, monkeypatch, capsys
):
    slug = slug_of(admin_conn, tenant_id)
    base = ["add-recipient", "--tenant-slug", slug, "--name", "Ana"]

    assert run(monkeypatch, admin_url, *base, "--phone", "123") == 2
    assert (
        run(
            monkeypatch,
            admin_url,
            "add-recipient",
            "--tenant-slug",
            "nao-existe",
            "--name",
            "Ana",
            "--phone",
            "5511999990102",
        )
        == 1
    )
    assert run(monkeypatch, admin_url, *base, "--phone", "5511999990102") == 0
    assert run(monkeypatch, admin_url, *base, "--phone", "5511999990102") == 1
    assert "ja cadastrado" in capsys.readouterr().err


def test_only_a_socio_user_can_be_linked(
    admin_url, admin_conn, tenant_id, make_user, monkeypatch, capsys
):
    slug = slug_of(admin_conn, tenant_id)
    socio = make_user(tenant_id, "socio", email="dono@exemplo.com")
    make_user(tenant_id, "gestor", ["fiscal"], email="gestor@exemplo.com")
    args = ["add-recipient", "--tenant-slug", slug, "--name", "X", "--phone", "5511999990103"]

    assert run(monkeypatch, admin_url, *args, "--user-email", "gestor@exemplo.com") == 2
    assert "socio" in capsys.readouterr().err
    assert run(monkeypatch, admin_url, *args, "--user-email", "dono@exemplo.com") == 0
    linked = admin_conn.execute(
        "SELECT user_id FROM agent_recipients WHERE phone = '5511999990103'"
    ).fetchone()[0]
    assert linked == socio.id


def test_remove_recipient_deactivates_it(admin_url, admin_conn, tenant_id, monkeypatch):
    slug = slug_of(admin_conn, tenant_id)
    add_recipient(admin_conn, tenant_id, "5511999990104")

    assert (
        run(
            monkeypatch,
            admin_url,
            "remove-recipient",
            "--tenant-slug",
            slug,
            "--phone",
            "5511999990104",
        )
        == 0
    )

    active = admin_conn.execute(
        "SELECT active FROM agent_recipients WHERE phone = '5511999990104'"
    ).fetchone()[0]
    assert active is False


def test_the_outbox_shows_what_the_agent_wrote_and_its_state(
    admin_url, admin_conn, tenant_id, monkeypatch, capsys
):
    slug = slug_of(admin_conn, tenant_id)
    recipient = add_recipient(admin_conn, tenant_id, "5511999990105", name="Carlos")
    admin_conn.execute(
        "INSERT INTO agent_notifications (tenant_id, recipient_id, kind, dedupe_key, body, status) "
        "VALUES (%s, %s, 'appointment', 'k1', 'Texto do aviso xyzoutbox', 'dry_run')",
        (tenant_id, recipient),
    )

    assert run(monkeypatch, admin_url, "agent-outbox", "--tenant-slug", slug) == 0

    out = capsys.readouterr().out
    assert "dry_run" in out and "appointment" in out and "Texto do aviso xyzoutbox" in out
    with pytest.raises(SystemExit):
        cli.main(["agent-outbox", "--limit", "0"])
