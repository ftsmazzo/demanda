from datetime import UTC, datetime, timedelta

from app.classification.llm import ClassifierUnavailable
from tests.agent_helpers import MON_MORNING, add_appointment, add_demand
from tests.nl_helpers import Chat, FakeIntentLLM, intent, named_user


def chat(database, conn, tenant_id, llm):
    return Chat(database, conn, tenant_id, llm)


def test_short_commands_never_spend_the_ai(database, admin_conn, tenant_id):
    llm = FakeIntentLLM(intent("summary"))
    talk = chat(database, admin_conn, tenant_id, llm)

    for text in ("agenda", "ajuda", "parado", "1", "2"):
        talk.say(text)

    assert llm.calls == []


def test_it_falls_back_to_i_did_not_understand_when_the_ai_cannot_help(
    database, admin_conn, tenant_id
):
    for llm in (
        None,
        FakeIntentLLM(error=ClassifierUnavailable("fora")),
        FakeIntentLLM(error=ValueError("fora do contrato")),
        FakeIntentLLM(intent("unknown")),
        FakeIntentLLM(intent("summary", confidence=0.2)),
    ):
        talk = Chat(database, admin_conn, tenant_id, llm, phone=f"55119999{id(llm) % 10**6:06d}")
        assert "Não entendi" in talk.say("blablabla xpto")


def test_the_daily_cap_stops_the_ai_but_not_the_commands(database, admin_conn, tenant_id):
    llm = FakeIntentLLM(intent("summary"))
    talk = chat(database, admin_conn, tenant_id, llm)

    first = talk.say("como estamos?", cap=1)
    second = talk.say("e agora?", cap=1)

    assert "Resumo agora" in first and "Não entendi" in second
    assert len(llm.calls) == 1
    assert "O que eu faço" in talk.say("ajuda", cap=1)


def test_the_ai_gets_the_team_names_and_the_local_date(database, admin_conn, tenant_id, make_user):
    named_user(make_user, admin_conn, tenant_id, "Ana Lima")
    llm = FakeIntentLLM(intent("summary"))
    talk = chat(database, admin_conn, tenant_id, llm)

    talk.say("como estamos?")

    _, ctx = llm.calls[0]
    assert "Ana Lima" in ctx.team and ctx.now.date().isoformat() == "2026-10-26"


def test_a_pending_task_wins_over_an_appointment_alert_for_the_same_one(
    database, admin_conn, tenant_id, make_user
):
    named_user(make_user, admin_conn, tenant_id, "Bruno Costa", sectors=("dp",))
    base = add_demand(admin_conn, tenant_id, title="Base", now=MON_MORNING)
    appointment = add_appointment(
        admin_conn,
        tenant_id,
        base,
        starts_at=datetime(2026, 10, 28, 17, 0, tzinfo=UTC),
        created_at=MON_MORNING - timedelta(hours=1),
        title="Reuniao",
    )
    llm = FakeIntentLLM(
        intent("create_task", title="Conferir a folha", assignee_name="Bruno", sector="dp")
    )
    talk = chat(database, admin_conn, tenant_id, llm)
    admin_conn.execute(
        "INSERT INTO agent_notifications (tenant_id, recipient_id, kind, dedupe_key, body, status, "
        "created_at) VALUES (%s, %s, 'appointment', %s, 'x', 'sent', %s)",
        (tenant_id, talk.recipient, str(appointment), MON_MORNING - timedelta(hours=1)),
    )
    talk.say("cria uma tarefa pro Bruno")

    talk.say("1")

    status = admin_conn.execute(
        "SELECT status FROM appointments WHERE id = %s", (appointment,)
    ).fetchone()[0]
    assert status == "proposed"  # o 1 foi da tarefa
    assert (
        talk.say("1") is not None and "Confirmado" in talk.sender.sent[-1][1]
    )  # agora o compromisso
