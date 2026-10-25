import json
from datetime import UTC, datetime

import pytest

from app.evolution_client import EvolutionClient, EvolutionError


class FakeTransport:
    def __init__(self, status=200, payload=None, error=None):
        self.status, self.payload, self.error = status, payload, error
        self.calls = []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, headers, body))
        if self.error:
            raise self.error
        return self.status, self.payload


def client(transport):
    return EvolutionClient("https://evo.example.com/", "chave-de-teste", transport=transport)


def test_connection_state_reads_the_state_and_sends_the_key():
    transport = FakeTransport(payload={"instance": {"instanceName": "esc", "state": "open"}})

    state = client(transport).connection_state("esc")

    method, url, headers, _ = transport.calls[0]
    assert (method, url) == ("GET", "https://evo.example.com/instance/connectionState/esc")
    assert headers["apikey"] == "chave-de-teste"
    assert state == "open"


def test_connection_state_is_unknown_when_the_instance_has_no_state():
    transport = FakeTransport(payload={"instance": {"instanceName": "esc"}})

    assert client(transport).connection_state("esc") == "unknown"


@pytest.mark.parametrize(
    "transport",
    [
        FakeTransport(error=OSError("sem rede")),
        FakeTransport(status=502, payload={}),
        FakeTransport(status=404, payload={}),
    ],
)
def test_connection_state_reports_unreachable_instead_of_raising(transport):
    assert client(transport).connection_state("esc") == "unreachable"


def test_instance_names_cannot_escape_the_path():
    transport = FakeTransport(payload={})

    assert client(transport).connection_state("../x") == "unreachable"
    assert transport.calls == []


def test_find_messages_sends_the_window_and_page_and_returns_records():
    records = [{"key": {"id": "A", "remoteJid": "5511@s.whatsapp.net"}}]
    body = {"total": 1, "pages": 1, "currentPage": 1, "records": records}
    transport = FakeTransport(payload={"messages": body})

    found, pages = client(transport).find_messages(
        "esc",
        since=datetime(2026, 10, 25, 10, tzinfo=UTC),
        until=datetime(2026, 10, 25, 12, tzinfo=UTC),
        page=2,
    )

    method, url, _, sent_body = transport.calls[0]
    assert (method, url) == ("POST", "https://evo.example.com/chat/findMessages/esc")
    sent = json.loads(sent_body)
    assert sent["page"] == 2
    assert sent["offset"] == 50
    assert sent["where"]["messageTimestamp"] == {
        "gte": "2026-10-25T10:00:00+00:00",
        "lte": "2026-10-25T12:00:00+00:00",
    }
    assert found == records
    assert pages == 1


def test_find_messages_raises_a_clear_error_on_failure():
    now = datetime.now(UTC)

    with pytest.raises(EvolutionError):
        client(FakeTransport(status=500, payload={})).find_messages("esc", since=now, until=now)
    with pytest.raises(EvolutionError):
        client(FakeTransport(error=OSError("x"))).find_messages("esc", since=now, until=now)
    with pytest.raises(EvolutionError):
        client(FakeTransport(payload={"outra": "coisa"})).find_messages("esc", since=now, until=now)
