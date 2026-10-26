from datetime import UTC, datetime, timedelta

from tests.agent_helpers import (
    MON_EVENING,
    MON_MORNING,
    FakeSender,
    add_appointment,
    add_demand,
    add_recipient,
    cycle,
    outbox,
)

PHONE_A, PHONE_B = "5511999990001", "5511999990002"


def setup_meeting(admin_conn, tenant_id, now, *, status="proposed", age_hours=1):
    demand = add_demand(admin_conn, tenant_id, title="Reuniao IE", sector="societario", now=now)
    return add_appointment(
        admin_conn,
        tenant_id,
        demand,
        starts_at=datetime(2026, 10, 28, 17, 0, tzinfo=UTC),  # quarta 14:00 em Sao Paulo
        created_at=now - timedelta(hours=age_hours),
        status=status,
        title="Vamos marcar a reuniao do projeto IE",
    )


def test_each_active_recipient_hears_about_a_new_proposed_appointment_once(
    database, admin_conn, tenant_id
):
    add_recipient(admin_conn, tenant_id, PHONE_A)
    add_recipient(admin_conn, tenant_id, PHONE_B)
    add_recipient(admin_conn, tenant_id, "5511999990003", active=False)
    setup_meeting(admin_conn, tenant_id, MON_MORNING)
    sender = FakeSender()

    cycle(database, tenant_id, sender, MON_MORNING)
    cycle(database, tenant_id, sender, MON_MORNING + timedelta(minutes=1))

    assert sorted(phone for phone, _ in sender.sent) == [PHONE_A, PHONE_B]
    text = sender.sent[0][1]
    assert "quarta-feira, 28/10 às 14:00" in text
    assert "projeto IE" in text
    assert "/agenda" in text


def test_old_confirmed_and_cancelled_appointments_are_not_announced(
    database, admin_conn, tenant_id
):
    add_recipient(admin_conn, tenant_id, PHONE_A)
    setup_meeting(admin_conn, tenant_id, MON_MORNING, age_hours=72)
    setup_meeting(admin_conn, tenant_id, MON_MORNING, status="confirmed")
    setup_meeting(admin_conn, tenant_id, MON_MORNING, status="cancelled")
    sender = FakeSender()

    cycle(database, tenant_id, sender, MON_MORNING)

    assert sender.sent == []


def test_nothing_goes_out_at_night_and_it_leaves_in_the_morning(database, admin_conn, tenant_id):
    add_recipient(admin_conn, tenant_id, PHONE_A)
    night = datetime(2026, 10, 27, 1, 30, tzinfo=UTC)  # 22:30 de segunda em Sao Paulo
    setup_meeting(admin_conn, tenant_id, night)
    sender = FakeSender()

    cycle(database, tenant_id, sender, night)
    assert sender.sent == []

    cycle(database, tenant_id, sender, datetime(2026, 10, 27, 11, 0, tzinfo=UTC))  # 08:00
    assert len(sender.sent) == 1


def test_a_failed_send_is_retried_later_and_gives_up_after_three_attempts(
    database, admin_conn, tenant_id
):
    add_recipient(admin_conn, tenant_id, PHONE_A)
    setup_meeting(admin_conn, tenant_id, MON_MORNING)
    broken = FakeSender(fail=True)

    cycle(database, tenant_id, broken, MON_MORNING)
    cycle(database, tenant_id, broken, MON_MORNING + timedelta(minutes=1))  # cedo demais
    assert outbox(admin_conn, tenant_id, "appointment")[0][1:3] == ("failed", 1)

    cycle(database, tenant_id, broken, MON_MORNING + timedelta(minutes=6))
    cycle(database, tenant_id, broken, MON_MORNING + timedelta(minutes=12))
    cycle(database, tenant_id, broken, MON_MORNING + timedelta(minutes=18))
    assert outbox(admin_conn, tenant_id, "appointment")[0][1:3] == ("failed", 3)

    healthy = FakeSender()
    cycle(database, tenant_id, healthy, MON_MORNING + timedelta(minutes=30))
    assert healthy.sent == []


def test_a_recovered_sender_delivers_the_retry(database, admin_conn, tenant_id):
    add_recipient(admin_conn, tenant_id, PHONE_A)
    setup_meeting(admin_conn, tenant_id, MON_MORNING)
    cycle(database, tenant_id, FakeSender(fail=True), MON_MORNING)
    sender = FakeSender()

    cycle(database, tenant_id, sender, MON_MORNING + timedelta(minutes=6))

    assert len(sender.sent) == 1
    assert outbox(admin_conn, tenant_id, "appointment")[0][1] == "sent"


def test_a_rehearsal_sender_records_the_text_and_marks_it_dry_run(database, admin_conn, tenant_id):
    add_recipient(admin_conn, tenant_id, PHONE_A)
    setup_meeting(admin_conn, tenant_id, MON_MORNING)
    rehearsal = FakeSender()
    rehearsal.mode = "dry_run"

    cycle(database, tenant_id, rehearsal, MON_MORNING)

    ((kind, status, _, body),) = outbox(admin_conn, tenant_id, "appointment")
    assert (kind, status) == ("appointment", "dry_run")
    assert "projeto IE" in body


def test_another_tenants_recipients_hear_nothing(database, admin_conn, tenant_id, other_channel):
    add_recipient(admin_conn, other_channel.tenant_id, PHONE_B)
    setup_meeting(admin_conn, tenant_id, MON_MORNING)
    sender = FakeSender()

    cycle(database, other_channel.tenant_id, sender, MON_EVENING)

    assert sender.sent == []
