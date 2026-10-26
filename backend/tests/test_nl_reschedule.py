from datetime import UTC, datetime

from tests.nl_helpers import Chat, FakeIntentLLM, contact, demand, intent

# segunda 26/10/2026, 09:05 em Sao Paulo. Quarta 14:00 = 17:00Z; quinta 15:00 = 18:00Z.
WED_14 = datetime(2026, 10, 28, 17, 0, tzinfo=UTC)
THU_15 = datetime(2026, 10, 29, 18, 0, tzinfo=UTC)


def chat(database, conn, tenant_id, *intents):
    return Chat(database, conn, tenant_id, FakeIntentLLM(*intents))


def appointment(conn, tenant_id, demand_id, title, starts_at=WED_14, status="confirmed"):
    return conn.execute(
        "INSERT INTO appointments (tenant_id, demand_id, title, starts_at, status) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (tenant_id, demand_id, title, starts_at, status),
    ).fetchone()[0]


def starts(conn, appointment_id):
    return conn.execute(
        "SELECT starts_at, all_day, status FROM appointments WHERE id = %s", (appointment_id,)
    ).fetchone()


def reschedule(**fields):
    return intent(
        "reschedule", case_text="reuniao do projeto", due_phrase="quinta as 15h", **fields
    )


def test_rescheduling_asks_with_the_old_and_new_time_then_moves_it_and_logs_it(
    database, admin_conn, tenant_id
):
    base = demand(admin_conn, tenant_id, "Reuniao do projeto IE")
    appt = appointment(admin_conn, tenant_id, base, "Reuniao do projeto IE")
    talk = chat(database, admin_conn, tenant_id, reschedule())

    proposal = talk.say("remarca a reuniao do projeto pra quinta as 15h")

    assert "Reuniao do projeto IE" in proposal
    assert "quarta-feira, 28/10" in proposal and "14:00" in proposal
    assert "quinta-feira, 29/10" in proposal and "15:00" in proposal
    assert starts(admin_conn, appt)[0] == WED_14

    reply = talk.say("1")

    assert starts(admin_conn, appt) == (THU_15, False, "confirmed")
    assert "quinta-feira, 29/10" in reply
    ((actor, kind, data),) = admin_conn.execute(
        "SELECT actor, kind, data FROM case_events WHERE demand_id = %s", (base,)
    ).fetchall()
    assert (actor, kind) == ("user", "appointment_updated")
    assert datetime.fromisoformat(data["before"]["starts_at"]) == WED_14
    assert datetime.fromisoformat(data["after"]["starts_at"]) == THU_15


def test_cancelling_the_proposal_leaves_the_appointment_alone(database, admin_conn, tenant_id):
    base = demand(admin_conn, tenant_id, "Reuniao do projeto IE")
    appt = appointment(admin_conn, tenant_id, base, "Reuniao do projeto IE")
    talk = chat(database, admin_conn, tenant_id, reschedule())
    talk.say("remarca a reuniao do projeto pra quinta as 15h")

    assert "Cancelado" in talk.say("2")

    assert starts(admin_conn, appt)[0] == WED_14


def test_the_client_name_finds_the_appointment_too(database, admin_conn, tenant_id):
    poli = contact(admin_conn, tenant_id, "Poli Silva")
    base = demand(admin_conn, tenant_id, "Encontro", contact_id=poli)
    appointment(admin_conn, tenant_id, base, "Encontro")
    talk = chat(
        database,
        admin_conn,
        tenant_id,
        intent("reschedule", case_text="poli", due_phrase="quinta as 15h"),
    )

    assert "Encontro" in talk.say("remarca o da Poli pra quinta as 15h")


def test_it_does_not_guess_when_nothing_or_many_match(database, admin_conn, tenant_id):
    base = demand(admin_conn, tenant_id, "Reuniao A")
    appointment(admin_conn, tenant_id, base, "Reuniao do projeto IE")
    appointment(admin_conn, tenant_id, base, "Reuniao do projeto Alfa")
    many = chat(database, admin_conn, tenant_id, reschedule())
    none = chat(
        database,
        admin_conn,
        tenant_id,
        intent("reschedule", case_text="vistoria", due_phrase="quinta as 15h"),
    )

    reply = many.say("remarca a reuniao do projeto pra quinta")

    assert "Reuniao do projeto IE" in reply and "Reuniao do projeto Alfa" in reply
    assert "mais detalhe" in reply
    assert "Não achei nenhum compromisso" in none.say("remarca a vistoria")


def test_cancelled_and_past_appointments_are_not_candidates(database, admin_conn, tenant_id):
    base = demand(admin_conn, tenant_id, "Reuniao base")
    appointment(admin_conn, tenant_id, base, "Reuniao do projeto IE", status="cancelled")
    past = datetime(2026, 10, 1, 17, 0, tzinfo=UTC)
    appointment(admin_conn, tenant_id, base, "Reuniao do projeto Beta", starts_at=past)
    talk = chat(database, admin_conn, tenant_id, reschedule())

    assert "Não achei nenhum compromisso" in talk.say("remarca a reuniao do projeto")


def test_an_unreadable_new_time_asks_instead_of_inventing(database, admin_conn, tenant_id):
    base = demand(admin_conn, tenant_id, "Reuniao do projeto IE")
    appt = appointment(admin_conn, tenant_id, base, "Reuniao do projeto IE")
    talk = chat(
        database,
        admin_conn,
        tenant_id,
        intent("reschedule", case_text="reuniao do projeto", due_phrase="quando der"),
    )

    reply = talk.say("remarca a reuniao do projeto pra quando der")

    assert "dia e a hora" in reply
    assert starts(admin_conn, appt)[0] == WED_14


def test_an_appointment_cancelled_before_the_yes_is_not_moved(database, admin_conn, tenant_id):
    base = demand(admin_conn, tenant_id, "Reuniao do projeto IE")
    appt = appointment(admin_conn, tenant_id, base, "Reuniao do projeto IE")
    talk = chat(database, admin_conn, tenant_id, reschedule())
    talk.say("remarca a reuniao do projeto pra quinta as 15h")
    admin_conn.execute("UPDATE appointments SET status = 'cancelled' WHERE id = %s", (appt,))

    reply = talk.say("1")

    assert "Não consegui" in reply
    assert starts(admin_conn, appt)[0] == WED_14
