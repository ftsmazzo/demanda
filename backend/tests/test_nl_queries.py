from datetime import UTC, datetime

from tests.agent_helpers import MON_MORNING, add_appointment
from tests.nl_helpers import Chat, FakeIntentLLM, contact, demand, intent, named_user


def chat(database, conn, tenant_id, *intents):
    return Chat(database, conn, tenant_id, FakeIntentLLM(*intents))


def test_what_does_a_person_have_lists_only_their_open_demands(
    database, admin_conn, tenant_id, make_user
):
    ana = named_user(make_user, admin_conn, tenant_id, "Ana Lima")
    bruno = named_user(make_user, admin_conn, tenant_id, "Bruno Costa")
    demand(admin_conn, tenant_id, "Folha de outubro", assignee=ana.id)
    demand(admin_conn, tenant_id, "Guia do DAS", assignee=ana.id)
    demand(admin_conn, tenant_id, "Balancete", assignee=bruno.id)
    demand(admin_conn, tenant_id, "Ja feita", assignee=ana.id, status="concluido")
    talk = chat(database, admin_conn, tenant_id, intent("query_demands", assignee_name="Ana"))

    reply = talk.say("o que a Ana tem pendente?")

    assert "Folha de outubro" in reply and "Guia do DAS" in reply
    assert "Balancete" not in reply and "Ja feita" not in reply
    assert "Ana Lima" in reply and "2 demandas" in reply


def test_an_unknown_or_ambiguous_person_is_not_guessed(database, admin_conn, tenant_id, make_user):
    named_user(make_user, admin_conn, tenant_id, "Ana Lima")
    named_user(make_user, admin_conn, tenant_id, "Ana Paula Souza")
    named_user(make_user, admin_conn, tenant_id, "Bruno Costa")
    nobody = chat(database, admin_conn, tenant_id, intent("query_demands", assignee_name="Zeca"))
    many = chat(database, admin_conn, tenant_id, intent("query_demands", assignee_name="Ana"))

    assert "Não encontrei ninguém chamado Zeca" in nobody.say("x")
    reply = many.say("x")
    assert "Ana Lima" in reply and "Ana Paula Souza" in reply and "qual" in reply.lower()


def test_stuck_filter_and_empty_answer(database, admin_conn, tenant_id):
    demand(admin_conn, tenant_id, "Parada ha dias", idle_hours=100, now=MON_MORNING)
    demand(admin_conn, tenant_id, "Recente", idle_hours=2, now=MON_MORNING)
    stuck = chat(database, admin_conn, tenant_id, intent("query_demands", status_filter="paradas"))
    waiting = chat(
        database, admin_conn, tenant_id, intent("query_demands", status_filter="aguardando")
    )

    reply = stuck.say("o que esta parado")

    assert "Parada ha dias" in reply and "Recente" not in reply
    assert "Nenhuma demanda" in waiting.say("o que esta aguardando")


def test_filter_by_client_ignores_accents_and_case(database, admin_conn, tenant_id):
    padaria = contact(admin_conn, tenant_id, "Padaria Pão Quente")
    demand(admin_conn, tenant_id, "Notas da padaria", contact_id=padaria)
    demand(admin_conn, tenant_id, "De outro cliente")
    talk = chat(
        database, admin_conn, tenant_id, intent("query_demands", contact_name="padaria pao quente")
    )

    reply = talk.say("o que tem da padaria")

    assert "Notas da padaria" in reply and "De outro cliente" not in reply


def test_priority_only_and_the_long_list_is_cut(database, admin_conn, tenant_id):
    vip = contact(admin_conn, tenant_id, "Cliente VIP", priority=True)
    for number in range(10):
        demand(admin_conn, tenant_id, f"Do vip {number}", contact_id=vip)
    demand(admin_conn, tenant_id, "Do comum")
    talk = chat(database, admin_conn, tenant_id, intent("query_demands", priority_only=True))

    reply = talk.say("so os prioritarios")

    assert "Do comum" not in reply and "10 demandas" in reply and "mais 2" in reply


def test_agenda_for_today_and_the_week(database, admin_conn, tenant_id):
    base = demand(admin_conn, tenant_id, "Base")
    for title, when, status in (
        ("Hoje as 15", datetime(2026, 10, 26, 18, 0, tzinfo=UTC), "confirmed"),
        ("Quarta as 10", datetime(2026, 10, 28, 13, 0, tzinfo=UTC), "proposed"),
        ("Cancelada", datetime(2026, 10, 26, 19, 0, tzinfo=UTC), "cancelled"),
        ("Mes que vem", datetime(2026, 11, 20, 13, 0, tzinfo=UTC), "confirmed"),
    ):
        add_appointment(
            admin_conn,
            tenant_id,
            base,
            starts_at=when,
            created_at=MON_MORNING,
            status=status,
            title=title,
        )
    today = chat(database, admin_conn, tenant_id, intent("query_agenda", range="today"))
    week = chat(database, admin_conn, tenant_id, intent("query_agenda", range="week"))

    today_text, week_text = today.say("agenda de hoje"), week.say("e a semana?")

    assert "Hoje as 15" in today_text and "Quarta as 10" not in today_text
    assert "Hoje as 15" in week_text and "Quarta as 10" in week_text
    assert "Cancelada" not in week_text and "Mes que vem" not in week_text


def test_summary_counts_come_from_the_database(database, admin_conn, tenant_id):
    demand(admin_conn, tenant_id, "Nova", status="novo")
    demand(admin_conn, tenant_id, "Andando", status="em_andamento", urgency="critica")
    demand(admin_conn, tenant_id, "Esperando", status="aguardando", idle_hours=100, now=MON_MORNING)
    demand(admin_conn, tenant_id, "Fechada", status="concluido")

    reply = chat(database, admin_conn, tenant_id, intent("summary")).say("como estamos?")

    assert "3 abertas" in reply and "1 crítica" in reply and "1 parada" in reply


def test_it_never_shows_another_tenants_data(database, admin_conn, tenant_id, other_channel):
    demand(admin_conn, other_channel.tenant_id, "Segredo do outro tenant")
    talk = chat(database, admin_conn, tenant_id, intent("query_demands", status_filter="abertas"))

    assert "Segredo do outro tenant" not in (talk.say("tudo") or "")
