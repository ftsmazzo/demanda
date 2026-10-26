import json

import pytest

from app.agent.sender import DryRunSender, EvolutionSender, SendError, build_sender
from app.evolution_client import EvolutionClient, EvolutionError
from tests.test_evolution_client import FakeTransport


def client(transport):
    return EvolutionClient("https://evo.example.com", "chave", transport=transport)


def test_send_text_posts_number_and_text_and_accepts_201():
    transport = FakeTransport(status=201, payload={"key": {"id": "X"}})

    client(transport).send_text("agente", "5511999990101", "Ola")

    method, url, headers, body = transport.calls[0]
    assert (method, url) == ("POST", "https://evo.example.com/message/sendText/agente")
    assert headers["apikey"] == "chave"
    assert json.loads(body) == {"number": "5511999990101", "text": "Ola"}


def test_send_text_failures_raise_a_clear_error():
    with pytest.raises(EvolutionError):
        client(FakeTransport(status=400, payload={})).send_text("agente", "5511", "x")
    with pytest.raises(EvolutionError):
        client(FakeTransport(error=OSError("rede"))).send_text("agente", "5511", "x")
    with pytest.raises(EvolutionError):
        client(FakeTransport(payload={})).send_text("../x", "5511", "x")


def test_the_evolution_sender_normalizes_the_number_and_wraps_errors():
    transport = FakeTransport(status=201, payload={})
    sender = EvolutionSender(client(transport), "agente")

    sender.send("+55 (11) 99999-0101", "Ola")

    assert json.loads(transport.calls[0][3])["number"] == "5511999990101"
    with pytest.raises(SendError):
        EvolutionSender(client(FakeTransport(status=500, payload={})), "agente").send("5511", "x")


def test_the_dry_run_sender_never_touches_the_network():
    sender = DryRunSender()

    sender.send("5511999990101", "Ola")

    assert sender.mode == "dry_run"


def test_build_sender_is_off_without_an_instance_and_safe_by_default():
    transport = FakeTransport(status=201, payload={})
    evolution = client(transport)

    assert build_sender({}, evolution) is None
    assert build_sender({"AGENT_INSTANCE": "agente"}, None) is None
    assert isinstance(build_sender({"AGENT_INSTANCE": "agente"}, evolution), DryRunSender)
    assert isinstance(
        build_sender({"AGENT_INSTANCE": "agente", "AGENT_SEND": "0"}, evolution), DryRunSender
    )
    live = build_sender({"AGENT_INSTANCE": "agente", "AGENT_SEND": "1"}, evolution)
    assert isinstance(live, EvolutionSender) and live.mode == "sent"
