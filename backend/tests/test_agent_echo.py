from uuid import uuid4

from app.agent.messages import AppointmentInfo, appointment_text
from app.classification.store import classify_pending
from app.core.demands import materialize_demands
from tests.agent_helpers import add_recipient
from tests.test_classification_service import FakeLLM, llm_output
from tests.test_classification_store import add_message

MEETING = FakeLLM(llm_output(sector="societario", kind="compromisso"))


def agent_alert_text(marker):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    info = AppointmentInfo(
        title=f"Vamos fazer uma reuniao sexta as 14 {marker}",
        starts_at=datetime(2026, 10, 30, 14, 0, tzinfo=ZoneInfo("America/Sao_Paulo")),
        all_day=False,
        contact_name="Poli",
        sector="Contábil",
    )
    return appointment_text(info, "https://demanda.example.com")


def record_sent(conn, tenant_id, body):
    recipient = add_recipient(conn, tenant_id, "55119" + str(uuid4().int)[:8])
    conn.execute(
        "INSERT INTO agent_notifications (tenant_id, recipient_id, kind, dedupe_key, body, status) "
        "VALUES (%s, %s, 'appointment', %s, %s, 'sent')",
        (tenant_id, recipient, uuid4().hex, body),
    )


def classification_of(conn, message_id):
    return conn.execute(
        "SELECT action, kind, reason FROM message_classifications WHERE message_id = %s",
        (message_id,),
    ).fetchone()


def test_a_message_that_is_the_agents_own_alert_is_noise_not_a_new_appointment(
    database, admin_conn, channel
):
    text = agent_alert_text("xyzecho1")
    record_sent(admin_conn, channel.tenant_id, text)
    message = add_message(admin_conn, channel, "ECO1", text, phone="5511900001111", minutes=0)

    classify_pending(database, channel.tenant_id, llm=MEETING)
    materialize_demands(database, channel.tenant_id)

    assert classification_of(admin_conn, message) == ("noise", "ruido", "agent_echo")
    demands = admin_conn.execute(
        "SELECT count(*) FROM demands WHERE tenant_id = %s AND title LIKE '%%xyzecho1%%'",
        (channel.tenant_id,),
    ).fetchone()[0]
    appointments = admin_conn.execute(
        "SELECT count(*) FROM appointments WHERE tenant_id = %s AND title LIKE '%%xyzecho1%%'",
        (channel.tenant_id,),
    ).fetchone()[0]
    assert (demands, appointments) == (0, 0)


def test_the_llm_is_not_even_called_for_an_echo(database, admin_conn, channel):
    text = agent_alert_text("xyzecho2")
    record_sent(admin_conn, channel.tenant_id, text)
    add_message(admin_conn, channel, "ECO2", text, phone="5511900002222", minutes=0)
    llm = FakeLLM(llm_output())

    classify_pending(database, channel.tenant_id, llm=llm)

    assert all("xyzecho2" not in call[0] for call in llm.calls)


def test_a_real_client_message_about_a_meeting_is_still_a_meeting(database, admin_conn, channel):
    message = add_message(
        admin_conn,
        channel,
        "REAL1",
        "Vamos fazer uma reuniao sexta as 14 xyzreal1",
        phone="5511900003333",
        minutes=0,
    )
    record_sent(admin_conn, channel.tenant_id, "Outro texto qualquer do agente")

    classify_pending(database, channel.tenant_id, llm=MEETING)

    assert classification_of(admin_conn, message)[0] == "classified"


def test_another_tenants_alert_text_does_not_silence_this_tenant(
    database, admin_conn, channel, other_channel
):
    text = agent_alert_text("xyzecho4")
    record_sent(admin_conn, other_channel.tenant_id, text)
    message = add_message(admin_conn, channel, "ECO4", text, phone="5511900004444", minutes=0)

    classify_pending(database, channel.tenant_id, llm=MEETING)

    assert classification_of(admin_conn, message)[0] == "classified"
