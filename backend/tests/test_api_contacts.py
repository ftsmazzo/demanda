import pytest

from tests.conftest import login_headers


@pytest.fixture
def team(tenant_id, make_user):
    return {
        "socio": make_user(tenant_id, "socio"),
        "gestor": make_user(tenant_id, "gestor", ["fiscal"]),
        "colab": make_user(tenant_id, "colaborador", ["fiscal"]),
    }


def new_contact(conn, tenant_id, phone, name=None, kind="desconhecido"):
    return conn.execute(
        "INSERT INTO contacts (tenant_id, phone, name, kind) VALUES (%s, %s, %s, %s) RETURNING id",
        (tenant_id, phone, name, kind),
    ).fetchone()[0]


def test_socio_and_gestor_list_contacts_but_colaborador_cannot(
    api_client, admin_conn, tenant_id, other_channel, team
):
    mine = new_contact(admin_conn, tenant_id, "5511000000001", "Padaria", "cliente")
    new_contact(admin_conn, other_channel.tenant_id, "5511000000002", "De outro tenant")

    for role in ("socio", "gestor"):
        response = api_client.get("/api/v1/contacts", headers=login_headers(api_client, team[role]))
        assert response.status_code == 200
        assert [item["id"] for item in response.json()] == [str(mine)]
    colab = login_headers(api_client, team["colab"])
    assert api_client.get("/api/v1/contacts", headers=colab).status_code == 403


def test_contacts_can_be_searched_and_filtered_without_wildcard_tricks(
    api_client, admin_conn, tenant_id, team
):
    new_contact(admin_conn, tenant_id, "5511000000011", "Padaria Pao Quente", "cliente")
    new_contact(admin_conn, tenant_id, "5511000000012", "Grafica Rapida", "fornecedor")
    new_contact(admin_conn, tenant_id, "5511000000013", None, "desconhecido")
    headers = login_headers(api_client, team["socio"])

    def names(query):
        response = api_client.get(f"/api/v1/contacts?{query}", headers=headers)
        assert response.status_code == 200, response.text
        return sorted(item["phone"] for item in response.json())

    assert names("q=padaria") == ["5511000000011"]
    assert names("q=000000012") == ["5511000000012"]
    assert names("kind=fornecedor") == ["5511000000012"]
    assert names("q=%25") == []
    assert names("q=_") == []
    assert len(names("limit=2")) == 2
    assert api_client.get("/api/v1/contacts?limit=1000", headers=headers).status_code == 422
    assert api_client.get("/api/v1/contacts?kind=inventado", headers=headers).status_code == 422


def test_name_and_kind_can_be_corrected_by_socio_and_gestor(
    api_client, admin_conn, tenant_id, team
):
    contact = new_contact(admin_conn, tenant_id, "5511000000021")

    response = api_client.patch(
        f"/api/v1/contacts/{contact}",
        json={"name": "  Clinica Vida  ", "kind": "cliente"},
        headers=login_headers(api_client, team["gestor"]),
    )

    body = response.json()
    assert response.status_code == 200
    assert (body["name"], body["kind"]) == ("Clinica Vida", "cliente")


def test_contact_edits_are_validated_and_restricted(
    api_client, admin_conn, tenant_id, other_channel, team
):
    contact = new_contact(admin_conn, tenant_id, "5511000000031")
    foreign = new_contact(admin_conn, other_channel.tenant_id, "5511000000032")
    socio = login_headers(api_client, team["socio"])
    url = f"/api/v1/contacts/{contact}"

    assert api_client.patch(url, json={}, headers=socio).status_code == 422
    assert api_client.patch(url, json={"kind": "alienigena"}, headers=socio).status_code == 422
    assert api_client.patch(url, json={"phone": "123"}, headers=socio).status_code == 422
    assert api_client.patch(url, json={"name": " "}, headers=socio).status_code == 422
    colab = login_headers(api_client, team["colab"])
    assert api_client.patch(url, json={"kind": "cliente"}, headers=colab).status_code == 403
    assert (
        api_client.patch(
            f"/api/v1/contacts/{foreign}", json={"kind": "cliente"}, headers=socio
        ).status_code
        == 404
    )
    assert api_client.get("/api/v1/contacts").status_code == 401


def test_users_list_for_assignment_hides_inactive_users_and_other_tenants(
    api_client, tenant_id, other_channel, make_user, team
):
    inactive = make_user(tenant_id, "colaborador", ["fiscal"], active=False)
    make_user(other_channel.tenant_id, "socio")

    response = api_client.get("/api/v1/users", headers=login_headers(api_client, team["gestor"]))

    body = response.json()
    assert response.status_code == 200
    listed = {item["id"] for item in body}
    assert listed == {str(team["socio"].id), str(team["gestor"].id), str(team["colab"].id)}
    assert str(inactive.id) not in listed
    gestor = next(item for item in body if item["id"] == str(team["gestor"].id))
    assert gestor["sectors"] == ["fiscal"]
    assert "email" not in gestor
    colab = login_headers(api_client, team["colab"])
    assert api_client.get("/api/v1/users", headers=colab).status_code == 403


def test_hr_sector_membership_is_hidden_from_people_without_hr_access(
    api_client, tenant_id, make_user, team
):
    hr_person = make_user(tenant_id, "colaborador", ["rh-interno", "fiscal"])

    def sectors_seen_by(viewer):
        response = api_client.get("/api/v1/users", headers=login_headers(api_client, viewer))
        return next(i["sectors"] for i in response.json() if i["id"] == str(hr_person.id))

    assert sectors_seen_by(team["socio"]) == ["fiscal", "rh-interno"]
    assert sectors_seen_by(team["gestor"]) == ["fiscal"]
