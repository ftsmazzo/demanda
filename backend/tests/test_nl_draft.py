import pytest

from app.agent.nl.contract import parse_intent
from tests.nl_helpers import Chat, FakeIntentLLM, demand, intent, named_user
from tests.test_nl_contract import good


def chat(database, conn, tenant_id, *intents):
    return Chat(database, conn, tenant_id, FakeIntentLLM(*intents))


def holiday_case(conn, tenant_id):
    case = demand(conn, tenant_id, "Ferias da Ana em dezembro")
    conn.execute(
        "UPDATE demands SET summary = %s, next_step = %s WHERE id = %s",
        ("Ana pediu ferias de 1 a 20 de dezembro.", "Lancar as ferias no sistema de RH.", case),
    )
    return case


def draft(**fields):
    return intent("draft_message", case_text="ferias da ana", assignee_name="Marcos", **fields)


def test_the_draft_is_shown_for_approval_and_only_then_handed_over(
    database, admin_conn, tenant_id, make_user
):
    named_user(make_user, admin_conn, tenant_id, "Marcos Souza")
    holiday_case(admin_conn, tenant_id)
    talk = chat(database, admin_conn, tenant_id, draft())

    proposal = talk.say("escreve pro Marcos lançar as férias da Ana")

    assert "Oi, Marcos!" in proposal and "Ferias da Ana em dezembro" in proposal
    assert "Ana pediu ferias de 1 a 20 de dezembro." in proposal
    assert "Responda 1" in proposal
    assert len(talk.sender.sent) == 1

    final = talk.say("1")

    assert "Oi, Marcos!" in final and "Lancar as ferias no sistema de RH." in final
    assert "repasse" in final.lower()


def test_nothing_is_ever_sent_to_anyone_but_the_partner_who_asked(
    database, admin_conn, tenant_id, make_user
):
    named_user(make_user, admin_conn, tenant_id, "Marcos Souza")
    holiday_case(admin_conn, tenant_id)
    talk = chat(database, admin_conn, tenant_id, draft())

    talk.say("escreve pro Marcos lançar as férias da Ana")
    talk.say("1")

    assert len(talk.sender.sent) == 2
    assert {phone for phone, _ in talk.sender.sent} == {talk.sender.sent[0][0]}


def test_cancelling_hands_over_nothing(database, admin_conn, tenant_id, make_user):
    named_user(make_user, admin_conn, tenant_id, "Marcos Souza")
    holiday_case(admin_conn, tenant_id)
    talk = chat(database, admin_conn, tenant_id, draft())
    talk.say("escreve pro Marcos lançar as férias da Ana")

    reply = talk.say("2")

    assert "Cancelado" in reply and "Lancar as ferias" not in reply


def test_an_unknown_person_or_case_is_not_guessed(database, admin_conn, tenant_id, make_user):
    named_user(make_user, admin_conn, tenant_id, "Marcos Souza")
    holiday_case(admin_conn, tenant_id)
    nobody = chat(
        database,
        admin_conn,
        tenant_id,
        intent("draft_message", case_text="ferias da ana", assignee_name="Zulmira"),
    )
    no_case = chat(
        database,
        admin_conn,
        tenant_id,
        intent("draft_message", case_text="rescisao", assignee_name="Marcos"),
    )

    assert "Não encontrei ninguém chamado Zulmira" in nobody.say("escreve pra Zulmira")
    assert "Não achei nenhuma demanda" in no_case.say("escreve sobre a rescisão")


def test_a_draft_request_needs_the_case_and_the_person():
    assert parse_intent(good(intent="draft_message", case_text="ferias", assignee_name="Marcos"))
    with pytest.raises(ValueError):
        parse_intent(good(intent="draft_message", case_text="ferias", assignee_name=None))
    with pytest.raises(ValueError):
        parse_intent(good(intent="draft_message", case_text=None, assignee_name="Marcos"))
