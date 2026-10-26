import uuid

from app import cli
from app.evolution_client import EvolutionClient
from app.provisioning import hash_secret
from tests.test_agent_webhook_setup import Evo

PASSWORD = "uma-senha-bem-longa-123"


HASH_SQL = (
    "SELECT webhook_secret_hash FROM channels c JOIN tenants t ON t.id = c.tenant_id "
    "WHERE t.slug = %s"
)


def unique(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def fresh_phone():
    return "55119" + str(uuid.uuid4().int)[:8]


def run(monkeypatch, admin_url, evo, args, **env):
    monkeypatch.setenv("DATABASE_URL", admin_url)
    monkeypatch.setenv("AGENT_APP_URL", "https://demanda.example.com/")
    monkeypatch.setenv("EVOLUTION_URL", "https://evo.example.com")
    monkeypatch.setenv("EVOLUTION_API_KEY", "chave")
    for key in ("USER_PASSWORD", "APP_URL"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(
        cli,
        "_evolution_from_env",
        lambda: EvolutionClient("https://evo.example.com", "k", transport=evo),
    )
    return cli.main(args)


def onboard_args(slug, instance, phone, email="dono@exemplo.com"):
    name = "Ecommtabil Contabilidade"
    return [
        "onboard-tenant",
        *("--slug", slug, "--name", name, "--instance", instance),
        *("--owner-name", "Eliezer Dono", "--owner-email", email, "--owner-phone", phone),
    ]


def sent_secret(evo):
    post = next(call for call in evo.calls if call[0] == "POST")
    return post[3]["webhook"]["headers"]["X-Webhook-Secret"]


def test_onboarding_creates_everything_and_wires_the_webhook(
    admin_url, admin_conn, monkeypatch, capsys, api_client
):
    slug, instance, phone = unique("ecom"), unique("inst"), fresh_phone()
    evo = Evo()

    code = run(
        monkeypatch, admin_url, evo, onboard_args(slug, instance, phone), USER_PASSWORD=PASSWORD
    )

    out = capsys.readouterr().out
    assert code == 0
    tenant = admin_conn.execute("SELECT id, name FROM tenants WHERE slug = %s", (slug,)).fetchone()
    assert tenant[1] == "Ecommtabil Contabilidade"
    channel_id, instance_name, stored_hash = admin_conn.execute(
        "SELECT id, instance_name, webhook_secret_hash FROM channels WHERE tenant_id = %s",
        (tenant[0],),
    ).fetchone()
    assert instance_name == instance
    body = next(call for call in evo.calls if call[0] == "POST")[3]["webhook"]
    assert body["url"] == f"https://demanda.example.com/webhooks/evolution/{channel_id}"
    assert body["events"] == ["MESSAGES_UPSERT"] and body["base64"] is False
    assert stored_hash == hash_secret(sent_secret(evo))
    user = admin_conn.execute(
        "SELECT id, role FROM users WHERE tenant_id = %s", (tenant[0],)
    ).fetchone()
    assert user[1] == "socio"
    recipient = admin_conn.execute(
        "SELECT phone, user_id FROM agent_recipients WHERE tenant_id = %s", (tenant[0],)
    ).fetchone()
    assert recipient == (phone, user[0])
    login = api_client.post(
        "/api/v1/auth/login",
        json={"tenant": slug, "email": "dono@exemplo.com", "password": PASSWORD},
    )
    assert login.status_code == 200
    assert PASSWORD not in out and sent_secret(evo) not in out
    assert slug in out and "webhooks/evolution" in out


def test_without_a_password_it_makes_one_and_shows_it_once(
    admin_url, admin_conn, monkeypatch, capsys, api_client
):
    slug = unique("ecom")

    code = run(monkeypatch, admin_url, Evo(), onboard_args(slug, unique("inst"), fresh_phone()))

    out = capsys.readouterr().out
    assert code == 0
    line = next(row for row in out.splitlines() if row.strip().startswith("senha inicial:"))
    password = line.split(":", 1)[1].strip()
    assert len(password) >= 12
    login = api_client.post(
        "/api/v1/auth/login",
        json={"tenant": slug, "email": "dono@exemplo.com", "password": password},
    )
    assert login.status_code == 200


def test_if_the_evolution_refuses_the_company_exists_and_the_message_says_how_to_finish(
    admin_url, admin_conn, monkeypatch, capsys
):
    slug = unique("ecom")

    code = run(
        monkeypatch,
        admin_url,
        Evo(set_status=401),
        onboard_args(slug, unique("inst"), fresh_phone()),
        USER_PASSWORD=PASSWORD,
    )

    err = capsys.readouterr().err
    assert code == 1
    assert "setup-channel-webhook" in err and slug in err
    assert (
        admin_conn.execute("SELECT count(*) FROM tenants WHERE slug = %s", (slug,)).fetchone()[0]
        == 1
    )


def test_an_existing_slug_creates_nothing_new(admin_url, admin_conn, monkeypatch, capsys):
    slug = unique("ecom")
    run(
        monkeypatch,
        admin_url,
        Evo(),
        onboard_args(slug, unique("inst"), fresh_phone()),
        USER_PASSWORD=PASSWORD,
    )
    capsys.readouterr()
    evo = Evo()

    code = run(
        monkeypatch,
        admin_url,
        evo,
        onboard_args(slug, unique("inst"), fresh_phone()),
        USER_PASSWORD=PASSWORD,
    )

    assert code == 1 and "ja existe" in capsys.readouterr().err
    assert [call for call in evo.calls if call[0] == "POST"] == []


def test_bad_input_is_refused_before_anything_is_created(
    admin_url, admin_conn, monkeypatch, capsys
):
    evo = Evo()
    good_phone = fresh_phone()

    assert (
        run(
            monkeypatch,
            admin_url,
            evo,
            onboard_args("Slug Invalido!", "inst", good_phone),
            USER_PASSWORD=PASSWORD,
        )
        == 2
    )
    assert (
        run(
            monkeypatch,
            admin_url,
            evo,
            onboard_args(unique("ecom"), "inst", "123"),
            USER_PASSWORD=PASSWORD,
        )
        == 2
    )
    assert (
        run(
            monkeypatch,
            admin_url,
            evo,
            onboard_args(unique("ecom"), "inst", good_phone),
            USER_PASSWORD="curta",
        )
        == 2
    )
    assert (
        run(
            monkeypatch,
            admin_url,
            evo,
            onboard_args(unique("ecom"), "../x", good_phone),
            USER_PASSWORD=PASSWORD,
        )
        == 2
    )
    assert [call for call in evo.calls if call[0] == "POST"] == []
    capsys.readouterr()


def test_setup_channel_webhook_rotates_the_secret_only_after_the_evolution_confirms(
    admin_url, admin_conn, monkeypatch, capsys
):
    slug = unique("ecom")
    run(
        monkeypatch,
        admin_url,
        Evo(),
        onboard_args(slug, unique("inst"), fresh_phone()),
        USER_PASSWORD=PASSWORD,
    )
    old_hash = admin_conn.execute(
        HASH_SQL,
        (slug,),
    ).fetchone()[0]

    failing = run(
        monkeypatch,
        admin_url,
        Evo(set_status=500),
        ["setup-channel-webhook", "--tenant-slug", slug],
    )
    unchanged = admin_conn.execute(
        HASH_SQL,
        (slug,),
    ).fetchone()[0]
    evo = Evo()
    ok = run(monkeypatch, admin_url, evo, ["setup-channel-webhook", "--tenant-slug", slug])
    rotated = admin_conn.execute(
        HASH_SQL,
        (slug,),
    ).fetchone()[0]

    assert failing == 1 and unchanged == old_hash
    assert ok == 0 and rotated == hash_secret(sent_secret(evo)) and rotated != old_hash
    assert (
        run(monkeypatch, admin_url, Evo(), ["setup-channel-webhook", "--tenant-slug", "nao-existe"])
        == 1
    )
