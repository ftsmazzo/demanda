from datetime import UTC, datetime, timedelta

import pytest

from tests.conftest import login_headers
from tests.test_api_visibility import new_demand


@pytest.fixture
def team(tenant_id, make_user):
    return {
        "socio": make_user(tenant_id, "socio"),
        "gestor": make_user(tenant_id, "gestor", ["fiscal"]),
        "colab": make_user(tenant_id, "colaborador", ["fiscal"]),
    }


def new_appointment(conn, tenant_id, demand_id, *, title="Reuniao", days=1, status="proposed"):
    starts = datetime.now(UTC).replace(microsecond=0) + timedelta(days=days)
    return conn.execute(
        "INSERT INTO appointments (tenant_id, demand_id, title, starts_at, status) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (tenant_id, demand_id, title, starts, status),
    ).fetchone()[0]


def titles(response):
    assert response.status_code == 200, response.text
    return [item["title"] for item in response.json()]


def test_the_agenda_lists_upcoming_appointments_in_order_without_cancelled_ones(
    api_client, admin_conn, tenant_id, team
):
    demand = new_demand(admin_conn, tenant_id)
    new_appointment(admin_conn, tenant_id, demand, title="B depois", days=3)
    new_appointment(admin_conn, tenant_id, demand, title="A antes", days=1)
    new_appointment(admin_conn, tenant_id, demand, title="Cancelada", days=2, status="cancelled")
    new_appointment(admin_conn, tenant_id, demand, title="Velha", days=-5)

    response = api_client.get(
        "/api/v1/appointments", headers=login_headers(api_client, team["socio"])
    )

    assert titles(response) == ["A antes", "B depois"]
    item = response.json()[0]
    assert {
        "id",
        "title",
        "starts_at",
        "all_day",
        "status",
        "demand_id",
        "sector",
        "contact",
    } <= set(item)


def test_filters_by_status_and_period(api_client, admin_conn, tenant_id, team):
    demand = new_demand(admin_conn, tenant_id)
    new_appointment(admin_conn, tenant_id, demand, title="Confirmada", days=1, status="confirmed")
    new_appointment(admin_conn, tenant_id, demand, title="Proposta", days=2)
    new_appointment(admin_conn, tenant_id, demand, title="Cancelada", days=3, status="cancelled")
    headers = login_headers(api_client, team["socio"])

    assert titles(api_client.get("/api/v1/appointments?status=confirmed", headers=headers)) == [
        "Confirmada"
    ]
    assert titles(api_client.get("/api/v1/appointments?status=cancelled", headers=headers)) == [
        "Cancelada"
    ]
    until = (datetime.now(UTC) + timedelta(days=1, hours=12)).isoformat().replace("+00:00", "Z")
    assert titles(api_client.get(f"/api/v1/appointments?until={until}", headers=headers)) == [
        "Confirmada"
    ]
    assert (
        api_client.get("/api/v1/appointments?status=inventado", headers=headers).status_code == 422
    )


def test_each_role_sees_only_the_appointments_of_demands_it_can_see(
    api_client, admin_conn, tenant_id, other_channel, team
):
    mine = new_demand(admin_conn, tenant_id, sector="fiscal")
    assigned = new_demand(admin_conn, tenant_id, sector="dp", assignee=team["colab"].id)
    hidden = new_demand(admin_conn, tenant_id, sector="dp")
    hr = new_demand(admin_conn, tenant_id, sector="rh-interno")
    foreign = new_demand(admin_conn, other_channel.tenant_id)
    new_appointment(admin_conn, tenant_id, mine, title="fiscal")
    new_appointment(admin_conn, tenant_id, assigned, title="atribuida")
    new_appointment(admin_conn, tenant_id, hidden, title="dp alheia")
    new_appointment(admin_conn, tenant_id, hr, title="rh")
    new_appointment(admin_conn, other_channel.tenant_id, foreign, title="outro tenant")

    def seen(name):
        return set(
            titles(
                api_client.get(
                    "/api/v1/appointments", headers=login_headers(api_client, team[name])
                )
            )
        )

    assert seen("socio") == {"fiscal", "atribuida", "dp alheia", "rh"}
    assert seen("gestor") == {"fiscal"}
    assert seen("colab") == {"atribuida"}


def test_a_manager_confirms_cancels_and_reschedules(api_client, admin_conn, tenant_id, team):
    demand = new_demand(admin_conn, tenant_id, sector="fiscal")
    appointment = new_appointment(admin_conn, tenant_id, demand)
    headers = login_headers(api_client, team["gestor"])
    url = f"/api/v1/appointments/{appointment}"

    confirmed = api_client.patch(url, json={"status": "confirmed"}, headers=headers)
    assert confirmed.status_code == 200 and confirmed.json()["status"] == "confirmed"

    moved = api_client.patch(
        url, json={"starts_at": "2026-11-05T17:00:00Z", "all_day": False}, headers=headers
    )
    assert moved.json()["starts_at"].startswith("2026-11-05T17:00:00")

    cancelled = api_client.patch(url, json={"status": "cancelled"}, headers=headers)
    assert cancelled.json()["status"] == "cancelled"


def test_a_collaborator_cannot_change_and_hidden_ones_look_missing(
    api_client, admin_conn, tenant_id, other_channel, team
):
    visible = new_demand(admin_conn, tenant_id, sector="fiscal", assignee=team["colab"].id)
    hidden = new_demand(admin_conn, tenant_id, sector="dp")
    foreign = new_demand(admin_conn, other_channel.tenant_id)
    mine = new_appointment(admin_conn, tenant_id, visible)
    other = new_appointment(admin_conn, tenant_id, hidden)
    far = new_appointment(admin_conn, other_channel.tenant_id, foreign)
    colab = login_headers(api_client, team["colab"])
    gestor = login_headers(api_client, team["gestor"])

    assert (
        api_client.patch(
            f"/api/v1/appointments/{mine}", json={"status": "confirmed"}, headers=colab
        ).status_code
        == 403
    )
    assert (
        api_client.patch(
            f"/api/v1/appointments/{other}", json={"status": "confirmed"}, headers=gestor
        ).status_code
        == 404
    )
    assert (
        api_client.patch(
            f"/api/v1/appointments/{far}", json={"status": "confirmed"}, headers=gestor
        ).status_code
        == 404
    )


def test_patch_validates_input_and_requires_login(api_client, admin_conn, tenant_id, team):
    demand = new_demand(admin_conn, tenant_id)
    appointment = new_appointment(admin_conn, tenant_id, demand)
    headers = login_headers(api_client, team["socio"])
    url = f"/api/v1/appointments/{appointment}"

    assert api_client.patch(url, json={}, headers=headers).status_code == 422
    assert api_client.patch(url, json={"status": "inventado"}, headers=headers).status_code == 422
    assert api_client.patch(url, json={"starts_at": None}, headers=headers).status_code == 422
    assert api_client.patch(url, json={"status": "confirmed"}).status_code == 401
    assert api_client.get("/api/v1/appointments").status_code == 401
