from tests.nl_helpers import Chat, FakeIntentLLM, contact, demand, intent, named_user


def chat(database, conn, tenant_id, *intents):
    return Chat(database, conn, tenant_id, FakeIntentLLM(*intents))


def row(conn, demand_id):
    return conn.execute(
        "SELECT assignee_id, status, closed_at FROM demands WHERE id = %s", (demand_id,)
    ).fetchone()


def events(conn, demand_id):
    return conn.execute(
        "SELECT actor, kind, data FROM case_events WHERE demand_id = %s ORDER BY created_at, id",
        (demand_id,),
    ).fetchall()


def test_assigning_a_demand_asks_then_changes_the_owner_and_records_it(
    database, admin_conn, tenant_id, make_user
):
    ana = named_user(make_user, admin_conn, tenant_id, "Ana Lima")
    target = demand(admin_conn, tenant_id, "Folha de outubro do Mercado")
    demand(admin_conn, tenant_id, "Outra coisa")
    talk = chat(
        database,
        admin_conn,
        tenant_id,
        intent("assign", case_text="folha de outubro", assignee_name="Ana"),
    )

    proposal = talk.say("passa a folha de outubro pra Ana")
    assert "Folha de outubro do Mercado" in proposal and "Ana Lima" in proposal
    assert row(admin_conn, target)[0] is None

    talk.say("1")

    assert row(admin_conn, target)[0] == ana.id
    ((actor, kind, data),) = events(admin_conn, target)
    assert (actor, kind) == ("user", "assigned") and data["to"] == "Ana Lima"


def test_an_ambiguous_or_missing_demand_is_not_guessed(database, admin_conn, tenant_id, make_user):
    named_user(make_user, admin_conn, tenant_id, "Ana Lima")
    demand(admin_conn, tenant_id, "Folha de setembro")
    demand(admin_conn, tenant_id, "Folha de outubro")
    many = chat(
        database, admin_conn, tenant_id, intent("assign", case_text="folha", assignee_name="Ana")
    )
    none = chat(
        database,
        admin_conn,
        tenant_id,
        intent("assign", case_text="balancete", assignee_name="Ana"),
    )

    reply = many.say("passa a folha pra Ana")

    assert "Folha de setembro" in reply and "Folha de outubro" in reply and "mais detalhe" in reply
    assert "Não achei nenhuma demanda" in none.say("passa o balancete pra Ana")


def test_closing_a_demand_sets_the_close_date_and_logs_it(database, admin_conn, tenant_id):
    target = demand(admin_conn, tenant_id, "Guia do DAS de outubro")
    talk = chat(
        database,
        admin_conn,
        tenant_id,
        intent("set_status", case_text="guia do das", status="concluido"),
    )

    proposal = talk.say("conclui a guia do DAS")
    assert "concluída" in proposal
    talk.say("1")

    _, status, closed_at = row(admin_conn, target)
    assert status == "concluido" and closed_at is not None
    assert events(admin_conn, target)[0][1] == "status_changed"


def test_marking_a_client_as_priority_needs_one_confirmation(database, admin_conn, tenant_id):
    padaria = contact(admin_conn, tenant_id, "Padaria Estrela")
    talk = chat(
        database,
        admin_conn,
        tenant_id,
        intent("mark_priority", contact_name="padaria", priority_value=True),
    )

    proposal = talk.say("marca a padaria como prioritaria")
    assert "Padaria Estrela" in proposal and "prioritário" in proposal
    assert (
        admin_conn.execute("SELECT priority FROM contacts WHERE id = %s", (padaria,)).fetchone()[0]
        is False
    )

    talk.say("1")

    assert (
        admin_conn.execute("SELECT priority FROM contacts WHERE id = %s", (padaria,)).fetchone()[0]
        is True
    )


def test_unmarking_and_unknown_clients(database, admin_conn, tenant_id):
    vip = contact(admin_conn, tenant_id, "Cliente VIP", priority=True)
    off = chat(
        database,
        admin_conn,
        tenant_id,
        intent("mark_priority", contact_name="vip", priority_value=False),
    )
    missing = chat(
        database,
        admin_conn,
        tenant_id,
        intent("mark_priority", contact_name="fantasma", priority_value=True),
    )

    off.say("tira a prioridade do vip")
    off.say("1")

    assert (
        admin_conn.execute("SELECT priority FROM contacts WHERE id = %s", (vip,)).fetchone()[0]
        is False
    )
    assert "Não encontrei nenhum cliente" in missing.say("marca o fantasma")


def test_changes_of_one_tenant_never_touch_another(database, admin_conn, tenant_id, other_channel):
    foreign = demand(admin_conn, other_channel.tenant_id, "Guia do DAS alheia")
    talk = chat(
        database,
        admin_conn,
        tenant_id,
        intent("set_status", case_text="guia do das", status="concluido"),
    )

    reply = talk.say("conclui a guia do das")

    assert "Não achei nenhuma demanda" in reply
    assert row(admin_conn, foreign)[1] != "concluido"
