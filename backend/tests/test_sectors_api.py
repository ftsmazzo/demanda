import psycopg
import pytest

from tests.conftest import login_headers

DEFAULTS = {
    "triagem",
    "fiscal",
    "contabil",
    "dp",
    "societario",
    "financeiro",
    "rh-interno",
    "consultoria",
}


def listing(api_client, user, **params):
    response = api_client.get(
        "/api/v1/sectors", headers=login_headers(api_client, user), params=params
    )
    assert response.status_code == 200
    return response.json()


def slugs(api_client, user, **params):
    return {item["slug"] for item in listing(api_client, user, **params)}


def create(api_client, user, **body):
    return api_client.post("/api/v1/sectors", json=body, headers=login_headers(api_client, user))


def change(api_client, user, slug, **body):
    return api_client.patch(
        f"/api/v1/sectors/{slug}", json=body, headers=login_headers(api_client, user)
    )


def new_demand(api_client, user, sector):
    return api_client.post(
        "/api/v1/demands",
        json={"title": "Parecer", "sector": sector},
        headers=login_headers(api_client, user),
    )


def test_a_new_tenant_starts_with_the_standard_sectors(api_client, tenant_id, make_user):
    socio = make_user(tenant_id, "socio")

    body = listing(api_client, socio)

    assert DEFAULTS <= {item["slug"] for item in body}
    by_slug = {item["slug"]: item for item in body}
    assert by_slug["dp"]["label"] == "Pessoal" and by_slug["dp"]["color"].startswith("#")
    assert by_slug["triagem"]["system"] is True and by_slug["consultoria"]["system"] is False


def test_only_a_socio_creates_a_sector_and_the_slug_comes_from_the_name(
    api_client, tenant_id, make_user
):
    socio = make_user(tenant_id, "socio")
    gestor = make_user(tenant_id, "gestor", ["fiscal"])

    denied = create(api_client, gestor, label="Jurídico")
    made = create(api_client, socio, label="Jurídico Trabalhista", color="#336699")

    assert denied.status_code == 403
    assert made.status_code == 201
    assert made.json()["slug"] == "juridico-trabalhista"
    assert made.json()["label"] == "Jurídico Trabalhista" and made.json()["color"] == "#336699"
    assert "juridico-trabalhista" in slugs(api_client, gestor)


def test_a_new_sector_can_be_used_by_demands_and_people(
    api_client, admin_conn, tenant_id, make_user
):
    socio = make_user(tenant_id, "socio")
    create(api_client, socio, label="Jurídico")

    made = new_demand(api_client, socio, "juridico")
    person = make_user(tenant_id, "colaborador", ["juridico"])

    assert made.status_code == 201 and made.json()["sector"] == "juridico"
    assert admin_conn.execute(
        "SELECT sector FROM user_sectors WHERE user_id = %s", (person.id,)
    ).fetchall() == [("juridico",)]


def test_names_and_colors_are_validated_and_not_duplicated(api_client, tenant_id, make_user):
    socio = make_user(tenant_id, "socio")

    assert create(api_client, socio, label="  ").status_code == 422
    assert create(api_client, socio, label="Algo", color="vermelho").status_code == 422
    assert create(api_client, socio, label="Fiscal").status_code == 409
    assert create(api_client, socio, label="fiscal").status_code == 409
    assert create(api_client, socio, label="Nova área").status_code == 201
    assert create(api_client, socio, label="Nova Área").status_code == 409
    assert create(api_client, socio, label="???").status_code == 422


def test_a_sector_can_be_renamed_and_recolored_but_keeps_its_slug(api_client, tenant_id, make_user):
    socio = make_user(tenant_id, "socio")

    changed = change(
        api_client, socio, "consultoria", label="Consultoria estratégica", color="#112233"
    )

    assert changed.status_code == 200
    assert changed.json()["slug"] == "consultoria"
    assert changed.json()["label"] == "Consultoria estratégica"
    assert change(api_client, socio, "nao-existe", label="X").status_code == 404
    assert change(api_client, socio, "fiscal").status_code == 422


def test_deactivating_hides_it_from_new_work_but_keeps_what_exists(
    api_client, admin_conn, tenant_id, make_user
):
    socio = make_user(tenant_id, "socio")
    create(api_client, socio, label="Jurídico")
    kept = new_demand(api_client, socio, "juridico").json()["id"]

    off = change(api_client, socio, "juridico", active=False)

    assert off.status_code == 200 and off.json()["active"] is False
    assert "juridico" not in slugs(api_client, socio)
    assert "juridico" in slugs(api_client, socio, include_inactive=True)
    assert new_demand(api_client, socio, "juridico").status_code == 422
    assert (
        admin_conn.execute("SELECT sector FROM demands WHERE id = %s", (kept,)).fetchone()[0]
        == "juridico"
    )
    assert change(api_client, socio, "juridico", active=True).json()["active"] is True
    assert new_demand(api_client, socio, "juridico").status_code == 201


def test_triagem_and_rh_interno_cannot_be_turned_off(api_client, tenant_id, make_user):
    socio = make_user(tenant_id, "socio")

    for slug in ("triagem", "rh-interno"):
        assert change(api_client, socio, slug, active=False).status_code == 409


def test_a_sector_of_another_tenant_is_invisible_and_unusable(
    api_client, tenant_id, other_channel, make_user
):
    socio = make_user(tenant_id, "socio")
    outsider = make_user(other_channel.tenant_id, "socio")
    create(api_client, socio, label="Jurídico")

    assert "juridico" not in slugs(api_client, outsider)
    assert new_demand(api_client, outsider, "juridico").status_code == 422
    assert change(api_client, outsider, "juridico", label="Roubado").status_code == 404


def test_the_internal_hr_sector_is_hidden_from_those_without_access(
    api_client, tenant_id, make_user
):
    gestor = make_user(tenant_id, "gestor", ["fiscal"])
    hr = make_user(tenant_id, "colaborador", ["rh-interno"])

    assert "rh-interno" not in slugs(api_client, gestor)
    assert "rh-interno" in slugs(api_client, hr)


def test_requires_login(api_client):
    assert api_client.get("/api/v1/sectors").status_code == 401
    assert api_client.post("/api/v1/sectors", json={"label": "X"}).status_code == 401


def test_the_database_refuses_a_sector_the_tenant_does_not_have(admin_conn, tenant_id):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        admin_conn.execute(
            "INSERT INTO demands (tenant_id, sector, kind, urgency, title) "
            "VALUES (%s, 'inexistente', 'tarefa', 'normal', 'X')",
            (tenant_id,),
        )
