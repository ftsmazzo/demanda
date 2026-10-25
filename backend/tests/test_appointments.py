from datetime import UTC, datetime
from uuid import uuid4

from app.classification.store import classify_pending
from app.core.demands import materialize_demands
from tests.test_classification_service import FakeLLM, llm_output
from tests.test_classification_store import add_message

MEETING = FakeLLM(llm_output(sector="societario", kind="compromisso"))
QUARTA = "Vamos marcar uma reuniao quarta as 14 "


def run(database, tenant_id, llm=MEETING):
    classify_pending(database, tenant_id, llm=llm)
    return materialize_demands(database, tenant_id)


def phone():
    return "55119" + str(uuid4().int)[:8]


def say(admin_conn, channel, message_id, text):
    # a mensagem e de terca 20/10/2026 09:00 em Sao Paulo
    add_message(admin_conn, channel, message_id, text, phone=phone(), minutes=0)


def appointments(admin_conn, tenant_id, marker):
    return admin_conn.execute(
        "SELECT starts_at, all_day, status, origin, demand_id, title "
        "FROM appointments WHERE tenant_id = %s AND title LIKE %s",
        (tenant_id, f"%{marker}%"),
    ).fetchall()


def test_a_meeting_message_with_day_and_time_becomes_a_proposed_appointment(
    database, admin_conn, channel
):
    say(admin_conn, channel, "AP1", QUARTA + "xyzreuniao1")

    run(database, channel.tenant_id)

    found = appointments(admin_conn, channel.tenant_id, "xyzreuniao1")
    assert len(found) == 1
    starts_at, all_day, status, origin, demand_id, _ = found[0]
    assert starts_at == datetime(2026, 10, 21, 17, 0, tzinfo=UTC)
    assert (all_day, status, origin) == (False, "proposed", "auto")
    sql = "SELECT kind FROM demands WHERE id = %s"
    assert admin_conn.execute(sql, (demand_id,)).fetchone()[0] == "compromisso"


def test_the_tenant_time_zone_decides_the_clock(database, admin_conn, channel):
    sql = "UPDATE tenants SET timezone = %s WHERE id = %s"
    admin_conn.execute(sql, ("America/Manaus", channel.tenant_id))
    say(admin_conn, channel, "AP2", QUARTA + "xyzreuniao2")

    run(database, channel.tenant_id)
    admin_conn.execute(sql, ("America/Sao_Paulo", channel.tenant_id))

    ((starts_at, *_),) = appointments(admin_conn, channel.tenant_id, "xyzreuniao2")
    assert starts_at == datetime(2026, 10, 21, 18, 0, tzinfo=UTC)  # 14h em Manaus (UTC-4)


def test_a_day_without_time_is_kept_as_all_day(database, admin_conn, channel):
    say(admin_conn, channel, "AP3", "Podemos marcar a reuniao na quinta xyzreuniao3")

    run(database, channel.tenant_id)

    ((starts_at, all_day, *_),) = appointments(admin_conn, channel.tenant_id, "xyzreuniao3")
    assert all_day is True
    assert starts_at == datetime(2026, 10, 22, 3, 0, tzinfo=UTC)  # 00:00 em Sao Paulo


def test_a_meeting_without_a_date_stays_a_plain_demand(database, admin_conn, channel):
    say(admin_conn, channel, "AP4", "Precisamos marcar uma reuniao xyzreuniao4")

    run(database, channel.tenant_id)

    assert appointments(admin_conn, channel.tenant_id, "xyzreuniao4") == []
    demands = admin_conn.execute(
        "SELECT count(*) FROM demands WHERE tenant_id = %s AND title LIKE '%%xyzreuniao4%%'",
        (channel.tenant_id,),
    ).fetchone()[0]
    assert demands == 1


def test_only_meetings_become_appointments(database, admin_conn, channel):
    say(admin_conn, channel, "AP5", "Quando vence o DAS dia 28 xyzreuniao5?")

    run(database, channel.tenant_id, llm=FakeLLM(llm_output(sector="fiscal", kind="duvida")))

    assert appointments(admin_conn, channel.tenant_id, "xyzreuniao5") == []


def test_running_again_does_not_duplicate(database, admin_conn, channel):
    say(admin_conn, channel, "AP6", QUARTA + "xyzreuniao6")

    run(database, channel.tenant_id)
    run(database, channel.tenant_id)

    assert len(appointments(admin_conn, channel.tenant_id, "xyzreuniao6")) == 1


def test_appointments_are_isolated_between_tenants(database, admin_conn, channel, other_channel):
    say(admin_conn, channel, "AP7", QUARTA + "xyzreuniao7")
    run(database, channel.tenant_id)

    with database.tenant_transaction(other_channel.tenant_id) as conn:
        seen = conn.execute(
            "SELECT count(*) FROM appointments WHERE title LIKE '%xyzreuniao7%'"
        ).fetchone()[0]

    assert seen == 0


def test_backfill_creates_appointments_for_meetings_that_were_already_demands(
    database, admin_conn, channel
):
    from app.core.appointments import backfill_appointments

    say(admin_conn, channel, "AP8", QUARTA + "xyzreuniao8")
    run(database, channel.tenant_id)
    admin_conn.execute(
        "DELETE FROM appointments WHERE tenant_id = %s AND title LIKE '%%xyzreuniao8%%'",
        (channel.tenant_id,),
    )

    created = backfill_appointments(database, channel.tenant_id)

    assert created >= 1
    assert len(appointments(admin_conn, channel.tenant_id, "xyzreuniao8")) == 1
    assert backfill_appointments(database, channel.tenant_id) == 0
