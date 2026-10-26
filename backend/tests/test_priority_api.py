import pytest

from tests.conftest import login_headers
from tests.test_api_visibility import new_demand
from tests.test_classification_store import add_message


@pytest.fixture
def team(tenant_id, make_user):
    return {
        "socio": make_user(tenant_id, "socio"),
        "gestor": make_user(tenant_id, "gestor", ["fiscal"]),
        "colab": make_user(tenant_id, "colaborador", ["fiscal"]),
    }


def contact(conn, channel, message_id, phone):
    message = add_message(conn, channel, message_id, "oi", phone=phone)
    sql = "SELECT contact_id FROM messages WHERE id = %s"
    return conn.execute(sql, (message,)).fetchone()[0]


def set_priority(conn, contact_id, value=True):
    conn.execute("UPDATE contacts SET priority = %s WHERE id = %s", (value, contact_id))


def board_titles(response):
    body = response.json()
    return [card["title"] for column in body["columns"] for card in column["demands"]]


def test_a_manager_marks_a_client_as_priority_and_the_contact_list_shows_it(
    api_client, admin_conn, channel, team
):
    vip = contact(admin_conn, channel, "PR1", "5511900020001")
    url = f"/api/v1/contacts/{vip}"

    done = api_client.patch(
        url, json={"priority": True}, headers=login_headers(api_client, team["gestor"])
    )
    listed = api_client.get(
        "/api/v1/contacts", headers=login_headers(api_client, team["socio"])
    ).json()

    assert done.status_code == 200 and done.json()["priority"] is True
    assert next(c for c in listed if c["id"] == str(vip))["priority"] is True


def test_a_collaborator_cannot_change_priority_and_bad_values_are_refused(
    api_client, admin_conn, channel, team
):
    vip = contact(admin_conn, channel, "PR2", "5511900020002")
    url = f"/api/v1/contacts/{vip}"

    assert (
        api_client.patch(
            url, json={"priority": True}, headers=login_headers(api_client, team["colab"])
        ).status_code
        == 403
    )
    socio = login_headers(api_client, team["socio"])
    assert api_client.patch(url, json={"priority": None}, headers=socio).status_code == 422
    assert api_client.patch(url, json={"priority": "sim"}, headers=socio).status_code == 422


def test_cards_carry_the_priority_of_their_contact(api_client, admin_conn, channel, team):
    vip = contact(admin_conn, channel, "PR3", "5511900020003")
    set_priority(admin_conn, vip)
    demand = new_demand(admin_conn, channel.tenant_id, contact_id=vip, title="Do prioritario")

    detail = api_client.get(
        f"/api/v1/demands/{demand}", headers=login_headers(api_client, team["socio"])
    ).json()

    assert detail["contact"]["priority"] is True


def test_priority_clients_come_first_among_equals_and_can_be_filtered(
    api_client, admin_conn, channel, team
):
    vip = contact(admin_conn, channel, "PR4", "5511900020004")
    common = contact(admin_conn, channel, "PR5", "5511900020005")
    set_priority(admin_conn, vip)
    new_demand(admin_conn, channel.tenant_id, contact_id=common, title="Comum xyzprio")
    new_demand(admin_conn, channel.tenant_id, contact_id=vip, title="Prioritario xyzprio")
    headers = login_headers(api_client, team["socio"])

    everything = [
        t for t in board_titles(api_client.get("/api/v1/board", headers=headers)) if "xyzprio" in t
    ]
    only = [
        t
        for t in board_titles(api_client.get("/api/v1/board?priority=true", headers=headers))
        if "xyzprio" in t
    ]
    listing = api_client.get("/api/v1/demands?priority=true", headers=headers).json()

    assert everything == ["Prioritario xyzprio", "Comum xyzprio"]
    assert only == ["Prioritario xyzprio"]
    assert all(card["contact"]["priority"] for card in listing)
    assert api_client.get("/api/v1/board?priority=talvez", headers=headers).status_code == 422
