import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.agent_helpers import FakeSender, add_recipient
from tests.test_agent_inbound import alerted

SECRET = "segredo-do-agente-com-bastante-entropia"


def payload(text, phone="5511999990001", message_id="WA1", from_me=False, event="messages.upsert"):
    return {
        "event": event,
        "data": {
            "key": {"id": message_id, "remoteJid": f"{phone}@s.whatsapp.net", "fromMe": from_me},
            "pushName": "Dono",
            "messageType": "conversation",
            "message": {"conversation": text},
            "messageTimestamp": 1_790_000_000,
        },
    }


@pytest.fixture
def sender():
    return FakeSender()


@pytest.fixture
def web(admin_url, sender):
    app = create_app(
        admin_url,
        agent_sender=sender,
        agent_webhook_secret=SECRET,
        agent_app_url="https://x.example",
        agent_interval_seconds=3600,
    )
    with TestClient(app) as client:
        yield client


def post(web, body, secret=SECRET):
    headers = {"X-Webhook-Secret": secret} if secret else {}
    return web.post("/webhooks/agent", json=body, headers=headers)


def test_the_secret_is_required(web):
    assert post(web, payload("1"), secret=None).status_code == 401
    assert post(web, payload("1"), secret="errado").status_code == 401


def test_the_endpoint_does_not_exist_when_the_agent_is_off(admin_url):
    with TestClient(create_app(admin_url)) as client:
        response = client.post(
            "/webhooks/agent", json=payload("1"), headers={"X-Webhook-Secret": "x"}
        )
    assert response.status_code == 404


def test_an_owner_answering_one_confirms_the_appointment(web, sender, admin_conn, tenant_id):
    phone = "55119" + "99990003"
    recipient = add_recipient(admin_conn, tenant_id, phone)
    appointment = alerted(admin_conn, tenant_id, recipient)

    response = post(web, payload("1", phone=phone, message_id="WA-OK"))

    assert response.status_code == 200
    status = admin_conn.execute(
        "SELECT status FROM appointments WHERE id = %s", (appointment,)
    ).fetchone()
    assert status[0] == "confirmed"
    assert sender.sent and sender.sent[0][0] == phone


def test_strangers_get_no_answer_and_no_information(web, sender):
    response = post(web, payload("1", phone="5511900000000", message_id="WA-X"))

    assert response.status_code == 200
    assert sender.sent == []


def test_what_the_agent_itself_sent_and_other_events_are_ignored(
    web, sender, admin_conn, tenant_id
):
    phone = "5511999990004"
    add_recipient(admin_conn, tenant_id, phone)

    post(web, payload("ajuda", phone=phone, message_id="WA-ME", from_me=True))
    post(web, payload("ajuda", phone=phone, message_id="WA-EV", event="connection.update"))

    assert sender.sent == []


def test_a_phone_registered_in_two_companies_is_not_guessed(
    web, sender, admin_conn, tenant_id, other_channel
):
    phone = "5511999990005"
    add_recipient(admin_conn, tenant_id, phone)
    add_recipient(admin_conn, other_channel.tenant_id, phone)

    post(web, payload("ajuda", phone=phone, message_id="WA-AMB"))

    assert sender.sent == []


def test_a_brazilian_number_with_or_without_the_ninth_digit_is_the_same_person(
    web, sender, admin_conn, tenant_id
):
    add_recipient(admin_conn, tenant_id, "5511999990006")

    post(web, payload("ajuda", phone="551199990006", message_id="WA-9"))

    assert len(sender.sent) == 1
    assert sender.sent[0][0] == "5511999990006"
