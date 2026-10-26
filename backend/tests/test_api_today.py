import pytest

from app.classification.store import classify_pending
from tests.conftest import login_headers
from tests.test_api_visibility import new_demand
from tests.test_classification_service import FakeLLM, llm_output
from tests.test_classification_store import add_message


@pytest.fixture
def team(tenant_id, make_user):
    return {
        "socio": make_user(tenant_id, "socio"),
        "gestor": make_user(tenant_id, "gestor", ["fiscal"]),
        "colab": make_user(tenant_id, "colaborador", ["fiscal"]),
    }


def age(conn, demand, hours):
    conn.execute(
        "UPDATE demands SET last_activity_at = now() - make_interval(hours => %s) WHERE id = %s",
        (hours, demand),
    )


def titles(items):
    return [item["title"] for item in items]


def test_today_gathers_what_needs_a_decision(api_client, admin_conn, tenant_id, team):
    review = new_demand(admin_conn, tenant_id, title="Revisar xyzhoje")
    admin_conn.execute(
        "UPDATE demands SET needs_review = true, review_reason = 'confirmar agrupamento' "
        "WHERE id = %s",
        (review,),
    )
    new_demand(admin_conn, tenant_id, title="Calma xyzhoje")
    urgent = new_demand(admin_conn, tenant_id, title="Urgente parada xyzhoje", urgency="critica")
    age(admin_conn, urgent, 30)
    fresh = new_demand(admin_conn, tenant_id, title="Urgente recente xyzhoje", urgency="critica")
    age(admin_conn, fresh, 2)
    meeting = new_demand(admin_conn, tenant_id, title="Base", kind="compromisso")
    admin_conn.execute(
        "INSERT INTO appointments (tenant_id, demand_id, title, starts_at, status) "
        "VALUES (%s, %s, 'Reuniao a aprovar xyzhoje', now() + interval '2 days', 'proposed'), "
        "(%s, %s, 'Ja confirmada xyzhoje', now() + interval '2 days', 'confirmed')",
        (tenant_id, meeting, tenant_id, meeting),
    )

    body = api_client.get("/api/v1/today", headers=login_headers(api_client, team["socio"])).json()

    assert "Revisar xyzhoje" in titles(body["needs_review"])
    assert "Calma xyzhoje" not in titles(body["needs_review"])
    assert titles(body["to_confirm"]) == ["Reuniao a aprovar xyzhoje"]
    attention = titles(body["attention"])
    assert "Urgente parada xyzhoje" in attention and "Urgente recente xyzhoje" not in attention
    assert {"open", "meetings_today"} <= set(body["counts"])


def test_a_priority_clients_pending_item_needs_attention_even_if_normal(
    api_client, admin_conn, tenant_id, team
):
    vip = admin_conn.execute(
        "INSERT INTO contacts (tenant_id, phone, name, priority) "
        "VALUES (%s, '5511900040001', 'VIP', true) RETURNING id",
        (tenant_id,),
    ).fetchone()[0]
    demand = new_demand(admin_conn, tenant_id, contact_id=vip, title="Do vip parada xyzvip")
    age(admin_conn, demand, 30)

    body = api_client.get("/api/v1/today", headers=login_headers(api_client, team["socio"])).json()

    assert "Do vip parada xyzvip" in titles(body["attention"])


def test_messages_waiting_for_triage_are_counted_for_managers_only(
    api_client, database, admin_conn, channel, team
):
    add_message(admin_conn, channel, "TD1", "preciso da guia xyztriagem", phone="5511900040002")
    classify_pending(database, channel.tenant_id, llm=FakeLLM(llm_output()))

    socio = api_client.get("/api/v1/today", headers=login_headers(api_client, team["socio"])).json()
    colab = api_client.get("/api/v1/today", headers=login_headers(api_client, team["colab"])).json()

    assert socio["waiting_triage"] >= 1 and colab["waiting_triage"] == 0


def test_today_respects_visibility_and_requires_login(
    api_client, admin_conn, tenant_id, other_channel, team
):
    hidden = new_demand(
        admin_conn, tenant_id, sector="dp", title="De outro setor xyzvis", urgency="critica"
    )
    age(admin_conn, hidden, 40)
    foreign = new_demand(
        admin_conn, other_channel.tenant_id, title="Alheia xyzvis", urgency="critica"
    )
    age(admin_conn, foreign, 40)

    gestor = api_client.get(
        "/api/v1/today", headers=login_headers(api_client, team["gestor"])
    ).json()
    socio = api_client.get("/api/v1/today", headers=login_headers(api_client, team["socio"])).json()

    assert "De outro setor xyzvis" not in titles(gestor["attention"])
    assert "De outro setor xyzvis" in titles(socio["attention"])
    assert "Alheia xyzvis" not in titles(socio["attention"])
    assert api_client.get("/api/v1/today").status_code == 401
