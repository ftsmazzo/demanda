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

PHONE = "5511999990001"


def test_the_daily_summary_goes_out_once_after_six_pm_on_weekdays(database, admin_conn, tenant_id):
    add_recipient(admin_conn, tenant_id, PHONE)
    now = MON_EVENING
    add_demand(
        admin_conn, tenant_id, title="Nova de hoje", created_at=now - timedelta(hours=2), now=now
    )
    add_demand(
        admin_conn,
        tenant_id,
        title="Fechada hoje",
        status="concluido",
        created_at=now - timedelta(days=2),
        now=now,
    )
    add_demand(admin_conn, tenant_id, title="Parada", idle_hours=100, urgency="critica", now=now)
    sender = FakeSender()

    def summaries():
        return [text for _, text in sender.sent if "Resumo do dia" in text]

    cycle(database, tenant_id, sender, now - timedelta(minutes=45))  # 17:45: cedo
    assert summaries() == []

    cycle(database, tenant_id, sender, now)
    cycle(database, tenant_id, sender, now + timedelta(minutes=1))

    assert len(summaries()) == 1
    text = summaries()[0]
    assert "Resumo do dia, segunda-feira, 26/10" in text
    assert "1 nova" in text and "1 concluída" in text
    assert "3 abertas" not in text and "2 abertas" in text
    assert "1 crítica" in text
    assert "Parada" in text


def test_the_summary_mentions_tomorrows_appointments(database, admin_conn, tenant_id):
    add_recipient(admin_conn, tenant_id, PHONE)
    demand = add_demand(admin_conn, tenant_id, title="Base", now=MON_EVENING)
    add_appointment(
        admin_conn,
        tenant_id,
        demand,
        starts_at=datetime(2026, 10, 27, 17, 0, tzinfo=UTC),  # terca 14:00 em Sao Paulo
        created_at=MON_EVENING - timedelta(days=3),
        status="confirmed",
        title="Reuniao do projeto IE",
    )
    sender = FakeSender()

    cycle(database, tenant_id, sender, MON_EVENING)

    assert "14:00 Reuniao do projeto IE" in sender.sent[0][1]


def test_no_summary_on_weekends_or_when_there_is_nothing_to_say(database, admin_conn, tenant_id):
    add_recipient(admin_conn, tenant_id, PHONE)
    sender = FakeSender()
    saturday = datetime(2026, 10, 31, 21, 30, tzinfo=UTC)
    add_demand(admin_conn, tenant_id, title="Qualquer", now=saturday)

    cycle(database, tenant_id, sender, saturday)
    assert sender.sent == []

    empty_tenant_day = datetime(2026, 10, 26, 21, 30, tzinfo=UTC)
    admin_conn.execute("DELETE FROM demands WHERE tenant_id = %s", (tenant_id,))
    cycle(database, tenant_id, sender, empty_tenant_day)
    assert sender.sent == []


def test_the_next_day_gets_its_own_summary(database, admin_conn, tenant_id):
    add_recipient(admin_conn, tenant_id, PHONE)
    add_demand(admin_conn, tenant_id, title="Aberta", now=MON_EVENING)
    sender = FakeSender()

    cycle(database, tenant_id, sender, MON_EVENING)
    cycle(database, tenant_id, sender, MON_EVENING + timedelta(days=1))

    assert len(sender.sent) == 2


def test_the_stuck_alert_comes_in_the_morning_and_lists_only_long_waits(
    database, admin_conn, tenant_id
):
    add_recipient(admin_conn, tenant_id, PHONE)
    now = MON_MORNING
    add_demand(admin_conn, tenant_id, title="Esquecida ha cinco dias", idle_hours=120, now=now)
    add_demand(admin_conn, tenant_id, title="Recente", idle_hours=5, now=now)
    add_demand(
        admin_conn,
        tenant_id,
        title="Antiga mas fechada",
        idle_hours=200,
        status="concluido",
        now=now,
    )
    sender = FakeSender()

    cycle(database, tenant_id, sender, now - timedelta(hours=2))  # 07:05: ainda cedo
    assert [kind for kind, *_ in outbox(admin_conn, tenant_id)] == []

    cycle(database, tenant_id, sender, now)
    cycle(database, tenant_id, sender, now + timedelta(minutes=1))

    assert len(sender.sent) == 1
    text = sender.sent[0][1]
    assert "Esquecida ha cinco dias" in text and "5 dias" in text
    assert "Recente" not in text and "Antiga mas fechada" not in text


def test_no_stuck_alert_when_nothing_is_stuck_and_it_does_not_check_again(
    database, admin_conn, tenant_id
):
    add_recipient(admin_conn, tenant_id, PHONE)
    add_demand(admin_conn, tenant_id, title="Recente", idle_hours=2, now=MON_MORNING)
    sender = FakeSender()

    cycle(database, tenant_id, sender, MON_MORNING)

    assert sender.sent == []
    assert [row[:2] for row in outbox(admin_conn, tenant_id, "stuck")] == [("stuck", "skipped")]


def fill_daily_cap(conn, tenant_id, recipient, kind, count, *, when=MON_MORNING):
    for number in range(count):
        conn.execute(
            "INSERT INTO agent_notifications (tenant_id, recipient_id, kind, dedupe_key, body, "
            "status, sent_at, created_at) VALUES (%s, %s, %s, %s, 'x', 'sent', %s, %s)",
            (tenant_id, recipient, kind, f"velho-{kind}-{number}", when, when),
        )


def test_a_recipient_over_the_daily_cap_is_not_flooded_and_nothing_is_lost(
    database, admin_conn, tenant_id
):
    recipient = add_recipient(admin_conn, tenant_id, PHONE)
    fill_daily_cap(admin_conn, tenant_id, recipient, "appointment", 20)
    add_demand(admin_conn, tenant_id, title="Esquecida", idle_hours=120, now=MON_MORNING)
    sender = FakeSender()

    cycle(database, tenant_id, sender, MON_MORNING + timedelta(minutes=1))

    assert sender.sent == []
    assert outbox(admin_conn, tenant_id, "stuck") == []  # nada foi descartado: so adiado

    # passadas 24 h, o limite folga e o aviso que ficou esperando sai
    later = MON_MORNING + timedelta(hours=24, minutes=5)
    cycle(database, tenant_id, sender, later)
    assert len(sender.sent) == 1 and "Esquecida" in sender.sent[0][1]


def test_replies_to_the_owner_do_not_use_up_the_alert_budget(database, admin_conn, tenant_id):
    recipient = add_recipient(admin_conn, tenant_id, PHONE)
    fill_daily_cap(admin_conn, tenant_id, recipient, "reply", 40)
    add_demand(admin_conn, tenant_id, title="Esquecida", idle_hours=120, now=MON_MORNING)
    sender = FakeSender()

    cycle(database, tenant_id, sender, MON_MORNING + timedelta(minutes=1))

    assert len(sender.sent) == 1
