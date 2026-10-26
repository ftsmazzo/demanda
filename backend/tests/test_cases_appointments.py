from datetime import UTC, datetime

from app.cases.service import materialize_cases
from tests.cases_helpers import FakeCaseLLM, decision, demands_of, events_of, phone, say

# as mensagens de teste sao de terca 20/10/2026 09:00 em Sao Paulo
WED_14 = datetime(2026, 10, 21, 17, 0, tzinfo=UTC)
THU_10 = datetime(2026, 10, 22, 13, 0, tzinfo=UTC)


def run(database, tenant_id, llm):
    return materialize_cases(database, tenant_id, llm)


def appointments(conn, tenant_id):
    return conn.execute(
        "SELECT id, starts_at, all_day, status, demand_id FROM appointments "
        "WHERE tenant_id = %s ORDER BY created_at, id",
        (tenant_id,),
    ).fetchall()


def meeting(**overrides):
    base = {
        "kind": "compromisso",
        "sector": "societario",
        "title": "Reuniao do projeto IE",
        "when_phrase": "quarta as 14",
    }
    base.update(overrides)
    return decision(**base)


def first_meeting(database, admin_conn, channel, who):
    say(admin_conn, channel, database, "Vamos marcar uma reuniao quarta as 14", who=who, minutes=0)
    run(database, channel.tenant_id, FakeCaseLLM(meeting()))
    ((appt_id, *_),) = appointments(admin_conn, channel.tenant_id)
    return appt_id


def test_a_new_meeting_creates_one_proposed_appointment_with_the_computed_date(
    database, admin_conn, channel
):
    say(admin_conn, channel, database, "Vamos marcar uma reuniao quarta as 14", who=phone())

    counts = run(database, channel.tenant_id, FakeCaseLLM(meeting()))

    ((_, starts_at, all_day, status, demand_id),) = appointments(admin_conn, channel.tenant_id)
    assert counts["appointment_created"] == 1
    assert (starts_at, all_day, status) == (WED_14, False, "proposed")
    assert "appointment_created" in [kind for _, kind, _ in events_of(admin_conn, demand_id)]


def test_a_confident_reschedule_updates_the_same_appointment_and_keeps_the_history(
    database, admin_conn, channel
):
    who = phone()
    appt_id = first_meeting(database, admin_conn, channel, who)
    admin_conn.execute("UPDATE appointments SET status = 'confirmed' WHERE id = %s", (appt_id,))
    say(admin_conn, channel, database, "Remarca pra quinta as 10", who=who, minutes=10)
    llm = FakeCaseLLM(
        meeting(
            action="attach",
            case_ref=1,
            appointment_ref=1,
            when_phrase="quinta as 10",
            confidence=0.9,
        )
    )

    counts = run(database, channel.tenant_id, llm)

    rows = appointments(admin_conn, channel.tenant_id)
    assert len(rows) == 1 and counts["appointment_updated"] == 1
    _, starts_at, _, status, demand_id = rows[0]
    assert (starts_at, status) == (THU_10, "proposed")
    event = next(e for e in events_of(admin_conn, demand_id) if e[1] == "appointment_updated")
    assert event[2]["before"]["status"] == "confirmed"
    assert event[2]["before"]["starts_at"].startswith("2026-10-21")
    assert event[2]["after"]["starts_at"].startswith("2026-10-22")
    assert llm.calls[0][1].appointments[0].status == "confirmed"


def test_an_unsure_reschedule_only_leaves_a_proposal_and_a_review_flag(
    database, admin_conn, channel
):
    who = phone()
    first_meeting(database, admin_conn, channel, who)
    say(admin_conn, channel, database, "Pode ser quinta as 10?", who=who, minutes=10)
    llm = FakeCaseLLM(
        meeting(
            action="attach",
            case_ref=1,
            appointment_ref=1,
            when_phrase="quinta as 10",
            confidence=0.7,
        )
    )

    counts = run(database, channel.tenant_id, llm)

    ((_, starts_at, _, status, demand_id),) = appointments(admin_conn, channel.tenant_id)
    assert counts["proposal"] == 1
    assert (starts_at, status) == (WED_14, "proposed")
    case = next(c for c in demands_of(admin_conn, channel.tenant_id, "projeto IE"))
    assert case[7] is True and "remarcacao" in case[8]
    proposal = next(e for e in events_of(admin_conn, demand_id) if e[1] == "proposal")
    assert proposal[2]["proposed"]["starts_at"].startswith("2026-10-22")


def test_a_phrase_without_a_usable_date_creates_no_appointment(database, admin_conn, channel):
    say(admin_conn, channel, database, "Vamos marcar uma reuniao em breve", who=phone())

    run(database, channel.tenant_id, FakeCaseLLM(meeting(when_phrase="em breve")))

    assert appointments(admin_conn, channel.tenant_id) == []


def test_only_meetings_get_appointments_even_if_the_ai_returns_a_phrase(
    database, admin_conn, channel
):
    say(admin_conn, channel, database, "O DAS vence na sexta", who=phone())

    run(
        database, channel.tenant_id, FakeCaseLLM(decision(kind="duvida", when_phrase="sexta as 10"))
    )

    assert appointments(admin_conn, channel.tenant_id) == []


def test_a_ref_to_a_cancelled_appointment_creates_a_new_one(database, admin_conn, channel):
    who = phone()
    appt_id = first_meeting(database, admin_conn, channel, who)
    say(admin_conn, channel, database, "Remarca pra quinta as 10", who=who, minutes=10)

    class CancellingLLM(FakeCaseLLM):
        def analyze(self, text, ctx):
            admin_conn.execute(
                "UPDATE appointments SET status = 'cancelled' WHERE id = %s", (appt_id,)
            )
            return super().analyze(text, ctx)

    llm = CancellingLLM(
        meeting(action="attach", case_ref=1, appointment_ref=1, when_phrase="quinta as 10")
    )

    run(database, channel.tenant_id, llm)

    rows = appointments(admin_conn, channel.tenant_id)
    assert [r[3] for r in rows] == ["cancelled", "proposed"]
    assert rows[1][1] == THU_10
