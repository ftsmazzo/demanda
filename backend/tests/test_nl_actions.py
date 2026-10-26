from datetime import date, timedelta

from tests.agent_helpers import MON_MORNING
from tests.nl_helpers import Chat, FakeIntentLLM, contact, intent, named_user


def chat(database, conn, tenant_id, *intents):
    return Chat(database, conn, tenant_id, FakeIntentLLM(*intents))


def tasks(conn, tenant_id, title):
    return conn.execute(
        "SELECT sector, kind, urgency, status, origin, assignee_id, due_date, contact_id, id "
        "FROM demands WHERE tenant_id = %s AND title = %s",
        (tenant_id, title),
    ).fetchall()


def create(**fields):
    base = {
        "title": "Conferir a folha",
        "assignee_name": "Bruno",
        "sector": "dp",
        "due_phrase": "sexta",
    }
    return intent("create_task", **{**base, **fields})


def test_a_task_request_only_proposes_and_one_creates_it(
    database, admin_conn, tenant_id, make_user
):
    bruno = named_user(make_user, admin_conn, tenant_id, "Bruno Costa", sectors=("dp",))
    talk = chat(database, admin_conn, tenant_id, create())

    proposal = talk.say("cria uma tarefa pro Bruno: conferir a folha, ate sexta")

    assert "Vou criar a tarefa" in proposal and "Conferir a folha" in proposal
    assert "Bruno Costa" in proposal and "sexta-feira, 30/10" in proposal
    assert "Responda 1 para confirmar ou 2 para cancelar" in proposal
    assert tasks(admin_conn, tenant_id, "Conferir a folha") == []

    done = talk.say("1")

    ((sector, kind, urgency, status, origin, assignee, due, _, demand_id),) = tasks(
        admin_conn, tenant_id, "Conferir a folha"
    )
    assert (sector, kind, status, origin, assignee) == ("dp", "tarefa", "novo", "manual", bruno.id)
    assert due == date(2026, 10, 30) and urgency == "normal"
    assert "Pronto" in done and "Bruno Costa" in done
    event = admin_conn.execute(
        "SELECT actor, kind FROM case_events WHERE demand_id = %s", (demand_id,)
    ).fetchone()
    assert event == ("user", "created")


def test_two_cancels_and_nothing_is_created(database, admin_conn, tenant_id, make_user):
    named_user(make_user, admin_conn, tenant_id, "Bruno Costa", sectors=("dp",))
    talk = chat(database, admin_conn, tenant_id, create())
    talk.say("cria uma tarefa")

    answer = talk.say("2")

    assert "Cancelado" in answer
    assert tasks(admin_conn, tenant_id, "Conferir a folha") == []
    assert "Não há compromisso" in talk.say("1")  # nada mais pendente


def test_a_confirmation_after_fifteen_minutes_does_nothing(
    database, admin_conn, tenant_id, make_user
):
    named_user(make_user, admin_conn, tenant_id, "Bruno Costa", sectors=("dp",))
    talk = chat(database, admin_conn, tenant_id, create())
    talk.say("cria uma tarefa", now=MON_MORNING)

    late = talk.say("1", now=MON_MORNING + timedelta(minutes=16))

    assert "Não há compromisso" in late
    assert tasks(admin_conn, tenant_id, "Conferir a folha") == []


def test_a_new_request_replaces_the_old_proposal(database, admin_conn, tenant_id, make_user):
    named_user(make_user, admin_conn, tenant_id, "Bruno Costa", sectors=("dp",))
    talk = chat(database, admin_conn, tenant_id, create(title="Primeira"), create(title="Segunda"))
    talk.say("primeira")
    talk.say("segunda")

    talk.say("1")

    assert tasks(admin_conn, tenant_id, "Primeira") == []
    assert len(tasks(admin_conn, tenant_id, "Segunda")) == 1


def test_unknown_assignee_or_client_asks_instead_of_guessing(
    database, admin_conn, tenant_id, make_user
):
    named_user(make_user, admin_conn, tenant_id, "Bruno Costa", sectors=("dp",))
    contact(admin_conn, tenant_id, "Padaria Estrela")
    contact(admin_conn, tenant_id, "Padaria Lua")
    nobody = chat(database, admin_conn, tenant_id, create(assignee_name="Zeca"))
    many = chat(database, admin_conn, tenant_id, create(contact_name="Padaria"))

    assert "Não encontrei ninguém chamado Zeca" in nobody.say("x")
    reply = many.say("x")
    assert "Padaria Estrela" in reply and "Padaria Lua" in reply
    assert tasks(admin_conn, tenant_id, "Conferir a folha") == []


def test_a_task_without_assignee_or_sector_still_works_and_priority_lifts_it(
    database, admin_conn, tenant_id
):
    vip = contact(admin_conn, tenant_id, "Mercado Bom Preço", priority=True)
    talk = chat(
        database,
        admin_conn,
        tenant_id,
        intent("create_task", title="Ligar para o cliente", contact_name="mercado bom preco"),
    )

    proposal = talk.say("liga pro mercado")
    talk.say("1")

    ((sector, _, urgency, _, _, assignee, _, contact_id, _),) = tasks(
        admin_conn, tenant_id, "Ligar para o cliente"
    )
    assert "sem responsável" in proposal
    assert (sector, assignee, contact_id) == ("triagem", None, vip) and urgency == "alta"
