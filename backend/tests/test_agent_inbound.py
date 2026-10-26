from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.agent.inbound import handle_inbound
from tests.agent_helpers import (
    MON_MORNING,
    URL,
    FakeSender,
    add_appointment,
    add_demand,
    add_recipient,
    outbox,
)

PHONE = "5511999990001"


def say(database, tenant_id, recipient, sender, text, *, message_id=None, now=MON_MORNING):
    return handle_inbound(
        database,
        sender,
        tenant_id=tenant_id,
        recipient_id=recipient,
        message_id=message_id or uuid4().hex,
        text=text,
        app_url=URL,
        now=now,
    )


def alerted(
    conn, tenant_id, recipient, *, title="Reuniao do projeto IE", status="proposed", hours=1
):
    demand = add_demand(conn, tenant_id, title="Base", now=MON_MORNING)
    appointment = add_appointment(
        conn,
        tenant_id,
        demand,
        starts_at=datetime(2026, 10, 28, 17, 0, tzinfo=UTC),
        created_at=MON_MORNING - timedelta(hours=hours),
        status=status,
        title=title,
    )
    conn.execute(
        "INSERT INTO agent_notifications (tenant_id, recipient_id, kind, dedupe_key, body, status, "
        "created_at, sent_at) VALUES (%s, %s, 'appointment', %s, 'x', 'sent', %s, %s)",
        (
            tenant_id,
            recipient,
            str(appointment),
            MON_MORNING - timedelta(hours=hours),
            MON_MORNING - timedelta(hours=hours),
        ),
    )
    return appointment


def status_of(conn, appointment):
    return conn.execute("SELECT status FROM appointments WHERE id = %s", (appointment,)).fetchone()[
        0
    ]


def test_one_confirms_the_appointment_the_agent_asked_about(database, admin_conn, tenant_id):
    recipient = add_recipient(admin_conn, tenant_id, PHONE)
    appointment = alerted(admin_conn, tenant_id, recipient)
    sender = FakeSender()

    say(database, tenant_id, recipient, sender, "1")

    assert status_of(admin_conn, appointment) == "confirmed"
    ((phone, text),) = sender.sent
    assert phone == PHONE
    assert "Confirmado" in text and "Reuniao do projeto IE" in text
    assert "quarta-feira, 28/10 às 14:00" in text


def test_two_cancels_it(database, admin_conn, tenant_id):
    recipient = add_recipient(admin_conn, tenant_id, PHONE)
    appointment = alerted(admin_conn, tenant_id, recipient)
    sender = FakeSender()

    say(database, tenant_id, recipient, sender, "2")

    assert status_of(admin_conn, appointment) == "cancelled"
    assert "Cancelado" in sender.sent[0][1]


def test_each_one_answers_the_next_pending_appointment(database, admin_conn, tenant_id):
    recipient = add_recipient(admin_conn, tenant_id, PHONE)
    first = alerted(admin_conn, tenant_id, recipient, title="Primeira", hours=3)
    second = alerted(admin_conn, tenant_id, recipient, title="Segunda", hours=1)
    sender = FakeSender()

    say(database, tenant_id, recipient, sender, "1")
    say(database, tenant_id, recipient, sender, "1")

    assert status_of(admin_conn, second) == "confirmed"
    assert status_of(admin_conn, first) == "confirmed"
    assert "Segunda" in sender.sent[0][1] and "Primeira" in sender.sent[1][1]


def test_answering_when_everything_is_settled_changes_nothing(database, admin_conn, tenant_id):
    recipient = add_recipient(admin_conn, tenant_id, PHONE)
    appointment = alerted(admin_conn, tenant_id, recipient, status="confirmed")
    sender = FakeSender()

    say(database, tenant_id, recipient, sender, "2")

    assert status_of(admin_conn, appointment) == "confirmed"
    assert "já estava confirmado" in sender.sent[0][1]


def test_without_any_alert_there_is_nothing_to_answer(database, admin_conn, tenant_id):
    recipient = add_recipient(admin_conn, tenant_id, PHONE)
    sender = FakeSender()

    say(database, tenant_id, recipient, sender, "1")

    assert "Não há compromisso" in sender.sent[0][1]


def test_a_redelivered_message_is_not_acted_on_twice(database, admin_conn, tenant_id):
    recipient = add_recipient(admin_conn, tenant_id, PHONE)
    alerted(admin_conn, tenant_id, recipient, title="Primeira", hours=3)
    alerted(admin_conn, tenant_id, recipient, title="Segunda", hours=1)
    sender = FakeSender()

    say(database, tenant_id, recipient, sender, "1", message_id="MSG-1")
    again = say(database, tenant_id, recipient, sender, "1", message_id="MSG-1")

    assert again is None
    assert len(sender.sent) == 1


def test_it_never_touches_another_tenants_appointments(
    database, admin_conn, tenant_id, other_channel
):
    mine = add_recipient(admin_conn, tenant_id, PHONE)
    theirs = add_recipient(admin_conn, other_channel.tenant_id, "5511999990002")
    foreign = alerted(admin_conn, other_channel.tenant_id, theirs)
    sender = FakeSender()

    say(database, tenant_id, mine, sender, "1")

    assert status_of(admin_conn, foreign) == "proposed"


def test_the_reply_is_recorded_and_a_failed_send_does_not_undo_the_action(
    database, admin_conn, tenant_id
):
    recipient = add_recipient(admin_conn, tenant_id, PHONE)
    appointment = alerted(admin_conn, tenant_id, recipient)

    say(database, tenant_id, recipient, FakeSender(fail=True), "1")

    assert status_of(admin_conn, appointment) == "confirmed"
    ((kind, status, attempts, body),) = outbox(admin_conn, tenant_id, "reply")
    assert (kind, status, attempts) == ("reply", "failed", 1)
    assert "Confirmado" in body


def test_asking_what_is_stuck_lists_the_longest_waits(database, admin_conn, tenant_id):
    recipient = add_recipient(admin_conn, tenant_id, PHONE)
    add_demand(admin_conn, tenant_id, title="Certidao negativa", idle_hours=100, now=MON_MORNING)
    add_demand(admin_conn, tenant_id, title="Recente", idle_hours=2, now=MON_MORNING)
    sender = FakeSender()

    say(database, tenant_id, recipient, sender, "o que está parado?")

    text = sender.sent[0][1]
    assert "Certidao negativa" in text and "Recente" not in text


def test_asking_what_is_stuck_when_nothing_is(database, admin_conn, tenant_id):
    recipient = add_recipient(admin_conn, tenant_id, PHONE)
    add_demand(admin_conn, tenant_id, title="Recente", idle_hours=2, now=MON_MORNING)
    sender = FakeSender()

    say(database, tenant_id, recipient, sender, "pendências")

    assert "Nada parado" in sender.sent[0][1]


def test_the_agenda_shows_today_and_tomorrow_without_cancelled_ones(
    database, admin_conn, tenant_id
):
    recipient = add_recipient(admin_conn, tenant_id, PHONE)
    demand = add_demand(admin_conn, tenant_id, title="Base", now=MON_MORNING)
    make = lambda title, when, status="confirmed": add_appointment(  # noqa: E731
        admin_conn,
        tenant_id,
        demand,
        starts_at=when,
        created_at=MON_MORNING - timedelta(days=2),
        status=status,
        title=title,
    )
    make("Hoje as 15", datetime(2026, 10, 26, 18, 0, tzinfo=UTC))
    make("Amanha as 10", datetime(2026, 10, 27, 13, 0, tzinfo=UTC), "proposed")
    make("Cancelada", datetime(2026, 10, 26, 19, 0, tzinfo=UTC), "cancelled")
    make("Depois de amanha", datetime(2026, 10, 28, 13, 0, tzinfo=UTC))
    sender = FakeSender()

    say(database, tenant_id, recipient, sender, "agenda")

    text = sender.sent[0][1]
    assert "15:00 Hoje as 15" in text and "10:00 Amanha as 10" in text
    assert "Cancelada" not in text and "Depois de amanha" not in text


def test_the_agenda_when_empty(database, admin_conn, tenant_id):
    recipient = add_recipient(admin_conn, tenant_id, PHONE)
    sender = FakeSender()

    say(database, tenant_id, recipient, sender, "agenda")

    assert "Nenhum compromisso" in sender.sent[0][1]


def test_help_and_unknown_texts_explain_what_the_agent_does(database, admin_conn, tenant_id):
    recipient = add_recipient(admin_conn, tenant_id, PHONE)
    sender = FakeSender()

    say(database, tenant_id, recipient, sender, "ajuda")
    say(database, tenant_id, recipient, sender, "banana azul")

    assert "1" in sender.sent[0][1] and "agenda" in sender.sent[0][1].lower()
    assert "ajuda" in sender.sent[1][1].lower()


def test_a_flood_of_messages_stops_getting_replies(database, admin_conn, tenant_id):
    recipient = add_recipient(admin_conn, tenant_id, PHONE)
    sender = FakeSender()

    for _ in range(70):
        say(database, tenant_id, recipient, sender, "ajuda")

    assert len(sender.sent) == 60
