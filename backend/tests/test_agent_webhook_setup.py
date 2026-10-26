import json

import pytest

from app import cli
from app.evolution_client import EvolutionClient, EvolutionError

SECRET = "segredo-longo-do-agente-0123456789"
ENV = {
    "DATABASE_URL": "postgresql://nao-usado",
    "EVOLUTION_URL": "https://evo.example.com",
    "EVOLUTION_API_KEY": "chave-da-evolution",
    "AGENT_INSTANCE": "secretaria",
    "AGENT_APP_URL": "https://demanda.example.com/",
    "AGENT_WEBHOOK_SECRET": SECRET,
}


class Evo:
    """Evolution de mentira: guarda o que recebeu e devolve o webhook gravado ao consultar."""

    def __init__(self, set_status=201, stored=None):
        self.calls = []
        self.set_status = set_status
        self.stored = stored

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, headers, json.loads(body) if body else None))
        if method == "POST":
            if self.set_status in (200, 201):
                self.stored = self.calls[-1][3]["webhook"]
            return self.set_status, {}
        return 200, self.stored or {}


def run(monkeypatch, evo, **overrides):
    env = {**ENV, **overrides}
    for key in ENV:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        if value is not None:
            monkeypatch.setenv(key, value)
    monkeypatch.setattr(
        cli,
        "_evolution_from_env",
        lambda: EvolutionClient("https://evo.example.com", "k", transport=evo),
    )
    return cli.main(["setup-agent-webhook"])


def test_it_sets_the_webhook_with_the_secret_header_and_the_right_events(monkeypatch, capsys):
    evo = Evo()

    code = run(monkeypatch, evo)

    out = capsys.readouterr().out
    assert code == 0
    method, url, headers, body = evo.calls[0]
    assert (method, url) == ("POST", "https://evo.example.com/webhook/set/secretaria")
    assert headers["apikey"] == "chave-da-evolution" or headers["apikey"] == "k"
    assert body == {
        "webhook": {
            "enabled": True,
            "url": "https://demanda.example.com/webhooks/agent",
            "headers": {"X-Webhook-Secret": SECRET},
            "byEvents": False,
            "base64": False,
            "events": ["MESSAGES_UPSERT"],
        }
    }
    assert "webhooks/agent" in out and "MESSAGES_UPSERT" in out
    assert SECRET not in out


def test_it_stops_and_lists_what_is_missing(monkeypatch, capsys):
    evo = Evo()

    code = run(monkeypatch, evo, AGENT_INSTANCE=None, AGENT_APP_URL=None)

    err = capsys.readouterr().err
    assert code == 2
    assert "AGENT_INSTANCE" in err and "AGENT_APP_URL" in err
    assert evo.calls == []


def test_without_a_secret_it_makes_one_and_asks_you_to_save_it_first(monkeypatch, capsys):
    evo = Evo()

    code = run(monkeypatch, evo, AGENT_WEBHOOK_SECRET=None)

    out = capsys.readouterr().out
    assert code == 2
    assert evo.calls == []
    generated = next(line for line in out.splitlines() if line.startswith("AGENT_WEBHOOK_SECRET="))
    assert len(generated.split("=", 1)[1]) >= 32


def test_an_evolution_refusal_is_reported_plainly(monkeypatch, capsys):
    code = run(monkeypatch, Evo(set_status=401))

    assert code == 1
    assert "HTTP 401" in capsys.readouterr().err


def test_it_warns_when_the_stored_webhook_is_not_what_was_asked(monkeypatch, capsys):
    class Forgetful(Evo):
        def __call__(self, method, url, headers, body):
            status, _ = super().__call__(method, url, headers, body)
            return (
                (status, {"enabled": False, "url": "https://outro", "events": []})
                if method == "GET"
                else (status, {})
            )

    code = run(monkeypatch, Forgetful())

    assert code == 1
    assert "nao confere" in capsys.readouterr().err.lower()


def test_client_methods_directly():
    evo = Evo()
    client = EvolutionClient("https://evo.example.com", "k", transport=evo)

    client.set_webhook(
        "secretaria", url="https://x/y", headers={"A": "b"}, events=["MESSAGES_UPSERT"]
    )
    found = client.find_webhook("secretaria")

    assert found["url"] == "https://x/y" and found["enabled"] is True
    with pytest.raises(EvolutionError):
        EvolutionClient("https://evo.example.com", "k", transport=Evo(set_status=500)).set_webhook(
            "secretaria", url="https://x", headers={}, events=[]
        )
