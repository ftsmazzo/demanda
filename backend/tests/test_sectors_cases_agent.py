import json

import pytest

from app.agent.nl.contract import parse_intent
from app.agent.nl.llm import IntentContext, OpenRouterIntentLLM
from app.cases.contract import parse_case_output
from app.cases.llm import OpenRouterCaseLLM
from app.cases.prompt import CaseContext
from tests.nl_helpers import Chat, FakeIntentLLM, intent
from tests.test_cases_llm import NOW
from tests.test_cases_llm import VALID as CASE_VALID
from tests.test_cases_llm import FakePost as CasePost
from tests.test_cases_llm import answer as case_answer
from tests.test_nl_contract import good
from tests.test_nl_llm import VALID as NL_VALID
from tests.test_nl_llm import FakePost as NlPost

INFOS = (("triagem", "Triagem"), ("fiscal", "Fiscal"), ("juridico", "Jurídico Trabalhista"))
CASE_CTX = CaseContext(None, "cliente", NOW, (), (), sectors=INFOS)
NL_CTX = IntentContext(now=NOW, team=("Ana Lima",), sectors=INFOS)


def test_the_case_ai_is_offered_the_tenants_sectors():
    post = CasePost(payload=case_answer({**CASE_VALID, "sector": "juridico"}))
    llm = OpenRouterCaseLLM(api_key="sk-or-teste", post=post)

    decision = llm.analyze("preciso de um advogado", CASE_CTX)

    body = post.calls[0][2]
    schema = body["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["sector"]["enum"] == ["triagem", "fiscal", "juridico"]
    assert "juridico (Jurídico Trabalhista)" in body["messages"][0]["content"]
    assert decision.sector == "juridico"


def test_the_case_ai_cannot_use_a_sector_the_tenant_turned_off():
    post = CasePost(payload=case_answer({**CASE_VALID, "sector": "consultoria"}))
    llm = OpenRouterCaseLLM(api_key="sk-or-teste", post=post)

    with pytest.raises(ValueError, match="setor invalido"):
        llm.analyze("preciso de um advogado", CASE_CTX)


def test_the_case_contract_defaults_to_the_standard_sectors():
    data = {**CASE_VALID, "sector": "consultoria"}

    assert parse_case_output(data, open_cases=0, appointments=0).sector == "consultoria"
    with pytest.raises(ValueError):
        parse_case_output(data, open_cases=0, appointments=0, sectors=("triagem",))


def test_the_agent_ai_is_offered_the_tenants_sectors_and_the_none_marker():
    post = NlPost(
        payload={
            "choices": [
                {
                    "message": {"content": json.dumps({**NL_VALID, "sector": "juridico"})},
                    "finish_reason": "stop",
                }
            ]
        }
    )
    llm = OpenRouterIntentLLM(api_key="sk-or-teste", post=post)

    result = llm.understand("cria uma tarefa juridica", NL_CTX)

    body = post.calls[0][2]
    enum = body["response_format"]["json_schema"]["schema"]["properties"]["sector"]["enum"]
    assert enum == ["triagem", "fiscal", "juridico", "none"]
    assert "juridico (Jurídico Trabalhista)" in body["messages"][0]["content"]
    assert result.sector == "juridico"


def test_the_agent_contract_checks_the_sector_against_the_tenants_list():
    data = good(intent="create_task", sector="consultoria")

    assert parse_intent(data).sector == "consultoria"
    with pytest.raises(ValueError):
        parse_intent(data, sectors=("triagem", "fiscal"))


def chat(database, conn, tenant_id, *intents):
    return Chat(database, conn, tenant_id, FakeIntentLLM(*intents))


def test_a_task_created_by_the_agent_can_go_to_a_custom_sector(database, admin_conn, tenant_id):
    admin_conn.execute(
        "INSERT INTO sectors (tenant_id, slug, label, color) VALUES (%s, 'juridico', "
        "'Jurídico', '#112233')",
        (tenant_id,),
    )
    talk = chat(
        database,
        admin_conn,
        tenant_id,
        intent("create_task", title="Revisar contrato", sector="juridico"),
    )

    proposal = talk.say("cria uma tarefa juridica: revisar contrato")
    talk.say("1")

    assert "Jurídico" in proposal
    row = admin_conn.execute(
        "SELECT sector FROM demands WHERE tenant_id = %s AND title = 'Revisar contrato'",
        (tenant_id,),
    ).fetchone()
    assert row == ("juridico",)


def test_a_task_aimed_at_a_turned_off_sector_goes_to_triagem(database, admin_conn, tenant_id):
    admin_conn.execute(
        "UPDATE sectors SET active = false WHERE tenant_id = %s AND slug = 'consultoria'",
        (tenant_id,),
    )
    talk = chat(
        database,
        admin_conn,
        tenant_id,
        intent("create_task", title="Parecer novo", sector="consultoria"),
    )

    proposal = talk.say("cria uma tarefa de consultoria: parecer novo")

    assert "Triagem" in proposal and "Consultoria" not in proposal
