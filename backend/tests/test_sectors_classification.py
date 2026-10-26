import json

import pytest

from app.classification.domain import Context
from app.classification.openrouter import OpenRouterClassifier
from app.classification.service import classify_message
from app.classification.store import classify_pending
from tests.test_classification_openrouter import FakePost, answer
from tests.test_classification_service import FakeLLM, llm_output
from tests.test_classification_store import add_message

INFOS = (("triagem", "Triagem"), ("fiscal", "Fiscal"), ("juridico", "Jurídico Trabalhista"))
VALID = {
    "sector": "juridico",
    "kind": "duvida",
    "urgency": "normal",
    "client_hint": None,
    "confidence": 0.9,
    "is_noise": False,
}


def run(post, context):
    return OpenRouterClassifier(api_key="sk-or-teste", post=post).classify(
        "Preciso de um advogado", context, {}
    )


def test_the_request_offers_the_tenants_sectors_in_the_schema_and_the_prompt():
    post = FakePost(payload=answer(VALID))

    out = run(post, Context(sectors=INFOS))

    body = post.calls[0][2]
    schema = body["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["sector"]["enum"] == ["triagem", "fiscal", "juridico"]
    assert "juridico (Jurídico Trabalhista)" in body["messages"][0]["content"]
    assert out.sector == "juridico"


def test_an_answer_outside_the_tenants_sectors_is_refused():
    post = FakePost(payload=answer({**VALID, "sector": "consultoria"}))

    with pytest.raises(ValueError, match="setor invalido"):
        run(post, Context(sectors=INFOS))


def test_without_the_tenants_list_the_standard_sectors_still_work():
    post = FakePost(payload=answer({**VALID, "sector": "fiscal"}))

    assert run(post, Context()).sector == "fiscal"
    assert "juridico" not in json.dumps(post.calls[0][2])


def test_a_sector_picked_by_rules_but_turned_off_goes_to_triagem():
    text = "Queria uma consultoria sobre planejamento tributario"
    on = classify_message(text, Context(sectors=(*INFOS, ("consultoria", "Consultoria"))), llm=None)
    off = classify_message(text, Context(sectors=INFOS), llm=None)

    assert on.classification.sector == "consultoria"
    assert off.classification.sector == "triagem"


def test_the_ai_choice_of_a_turned_off_sector_goes_to_triagem():
    llm = FakeLLM(llm_output(sector="consultoria"))

    decision = classify_message("preciso de ajuda com uma coisa", Context(sectors=INFOS), llm=llm)

    assert decision.classification.sector == "triagem"


def test_the_stored_flow_hands_the_ai_the_tenants_active_sectors(
    database, admin_conn, channel, tenant_id
):
    admin_conn.execute(
        "INSERT INTO sectors (tenant_id, slug, label, color) VALUES (%s, 'juridico', "
        "'Jurídico', '#112233')",
        (tenant_id,),
    )
    admin_conn.execute(
        "UPDATE sectors SET active = false WHERE tenant_id = %s AND slug = 'consultoria'",
        (tenant_id,),
    )
    add_message(admin_conn, channel, "SC1", "preciso de uma coisa qualquer xyzsetor")
    llm = FakeLLM(llm_output())

    classify_pending(database, channel.tenant_id, llm=llm)

    slugs = {slug for slug, _ in llm.calls[0][1].sectors}
    assert "juridico" in slugs and "consultoria" not in slugs and "triagem" in slugs
