import pytest

from app.agent.runner import SECTOR_LABEL
from app.cases.prompt import SYSTEM_PROMPT as CASE_PROMPT
from app.classification.domain import SECTORS, Context
from app.classification.llm import SYSTEM_PROMPT as CLASSIFY_PROMPT
from app.classification.rules import classify_by_rules
from tests.conftest import login_headers


def test_consultoria_is_a_known_sector_with_a_label_and_prompt_guidance():
    assert "consultoria" in SECTORS
    assert SECTOR_LABEL["consultoria"] == "Consultoria"
    assert "consultoria" in CLASSIFY_PROMPT and "consultoria" in CASE_PROMPT


@pytest.mark.parametrize(
    "text",
    [
        "Queria uma consultoria sobre planejamento tributario",
        "Preciso de um parecer sobre a viabilidade de abrir outra loja",
        "Podem fazer um diagnostico financeiro da empresa?",
    ],
)
def test_advisory_requests_land_in_consultoria(text):
    assert classify_by_rules(text, Context()).sector == "consultoria"


@pytest.mark.parametrize(
    ("text", "sector"),
    [
        ("Quando vence o DAS esse mes?", "fiscal"),
        ("Preciso da folha de pagamento de outubro", "dp"),
        ("Segue boleto da internet, vence dia 10", "financeiro"),
    ],
)
def test_the_other_sectors_are_not_stolen(text, sector):
    assert classify_by_rules(text, Context()).sector == sector


def test_the_database_accepts_the_sector_everywhere(admin_conn, tenant_id, make_user):
    user = make_user(tenant_id, "colaborador", ["consultoria"])
    demand = admin_conn.execute(
        "INSERT INTO demands (tenant_id, sector, kind, urgency, title) "
        "VALUES (%s, 'consultoria', 'tarefa', 'normal', 'Parecer') RETURNING id",
        (tenant_id,),
    ).fetchone()[0]
    sectors = admin_conn.execute(
        "SELECT sector FROM user_sectors WHERE user_id = %s", (user.id,)
    ).fetchall()

    assert demand is not None and sectors == [("consultoria",)]


def test_the_api_creates_and_filters_consultoria_demands(api_client, tenant_id, make_user):
    socio = make_user(tenant_id, "socio")
    headers = login_headers(api_client, socio)

    created = api_client.post(
        "/api/v1/demands",
        json={"title": "Parecer sobre a loja nova", "sector": "consultoria"},
        headers=headers,
    )
    board = api_client.get("/api/v1/board?sector=consultoria", headers=headers).json()

    assert created.status_code == 201
    titles = [d["title"] for col in board["columns"] for d in col["demands"]]
    assert "Parecer sobre a loja nova" in titles
