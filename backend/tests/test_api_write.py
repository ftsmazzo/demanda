import pytest

from tests.conftest import login_headers
from tests.test_api_visibility import new_demand, team  # noqa: F401


def create(client, headers, **body):
    payload = {"title": "Conferir o balancete", "sector": "contabil", **body}
    return client.post("/api/v1/demands", json=payload, headers=headers)


def patch(client, headers, demand_id, **body):
    return client.patch(f"/api/v1/demands/{demand_id}", json=body, headers=headers)


def test_socio_creates_a_manual_demand(api_client, team):  # noqa: F811
    headers = login_headers(api_client, team["socio"])

    response = create(api_client, headers, urgency="alta", due_date="2026-12-31")

    body = response.json()
    assert response.status_code == 201
    assert (body["origin"], body["status"], body["kind"], body["urgency"]) == (
        "manual",
        "novo",
        "tarefa",
        "alta",
    )
    assert body["due_date"] == "2026-12-31"
    listed = api_client.get("/api/v1/demands", headers=headers).json()
    assert [item["id"] for item in listed] == [body["id"]]


def test_gestor_creates_only_in_his_own_sectors_and_colaborador_cannot_create(
    api_client,
    team,  # noqa: F811
):
    gestor = login_headers(api_client, team["gestor"])
    colab = login_headers(api_client, team["colab"])

    assert create(api_client, gestor, sector="fiscal").status_code == 201
    assert create(api_client, gestor, sector="dp").status_code == 403
    assert create(api_client, colab, sector="fiscal").status_code == 403


@pytest.mark.parametrize(
    "body",
    [
        {"title": ""},
        {"title": "x" * 201},
        {"sector": "marketing"},
        {"kind": "outro"},
        {"urgency": "maxima"},
        {"due_date": "31/12/2026"},
        {"status": "concluido"},
    ],
)
def test_create_validates_input(api_client, team, body):  # noqa: F811
    headers = login_headers(api_client, team["socio"])

    assert create(api_client, headers, **body).status_code == 422


def test_create_rejects_bad_references(
    api_client,
    admin_conn,
    tenant_id,
    other_channel,
    make_user,
    team,  # noqa: F811
):
    headers = login_headers(api_client, team["socio"])
    foreign_user = make_user(other_channel.tenant_id)
    inactive = make_user(tenant_id, "colaborador", ["fiscal"], active=False)
    no_hr_access = make_user(tenant_id, "colaborador", ["fiscal"])
    foreign_contact = admin_conn.execute(
        "INSERT INTO contacts (tenant_id, phone) VALUES (%s, '5599000000001') RETURNING id",
        (other_channel.tenant_id,),
    ).fetchone()[0]

    assert create(api_client, headers, assignee_id=str(foreign_user.id)).status_code == 422
    assert create(api_client, headers, assignee_id=str(inactive.id)).status_code == 422
    hr = create(api_client, headers, sector="rh-interno", assignee_id=str(no_hr_access.id))
    assert hr.status_code == 422
    assert create(api_client, headers, contact_id=str(foreign_contact)).status_code == 422
    unknown = "00000000-0000-0000-0000-000000000000"
    assert create(api_client, headers, contact_id=unknown).status_code == 422


def test_create_with_a_valid_assignee_and_contact(
    api_client,
    admin_conn,
    tenant_id,
    team,  # noqa: F811
):
    headers = login_headers(api_client, team["socio"])
    contact = admin_conn.execute(
        "INSERT INTO contacts (tenant_id, phone, name) VALUES (%s, '5599000000002', 'Cliente') "
        "RETURNING id",
        (tenant_id,),
    ).fetchone()[0]

    response = create(
        api_client, headers, assignee_id=str(team["colab"].id), contact_id=str(contact)
    )

    body = response.json()
    assert response.status_code == 201
    assert body["assignee"]["id"] == str(team["colab"].id)
    assert body["contact"]["name"] == "Cliente"


def test_status_changes_set_and_clear_closed_at_and_count_as_activity(
    api_client,
    admin_conn,
    tenant_id,
    team,  # noqa: F811
):
    demand = new_demand(admin_conn, tenant_id)
    admin_conn.execute(
        "UPDATE demands SET last_activity_at = now() - interval '5 days' WHERE id = %s", (demand,)
    )
    headers = login_headers(api_client, team["socio"])

    closed = patch(api_client, headers, demand, status="concluido").json()
    assert closed["status"] == "concluido"
    assert closed["closed_at"] is not None
    assert closed["idle_hours"] < 1

    reopened = patch(api_client, headers, demand, status="em_andamento").json()
    assert reopened["closed_at"] is None


def test_socio_edits_every_field_and_can_clear_the_assignee(
    api_client,
    admin_conn,
    tenant_id,
    team,  # noqa: F811
):
    demand = new_demand(admin_conn, tenant_id, assignee=team["colab"].id)
    headers = login_headers(api_client, team["socio"])

    edited = patch(
        api_client,
        headers,
        demand,
        title="Novo titulo",
        urgency="critica",
        due_date="2026-11-30",
        sector="dp",
        assignee_id=str(team["gestor"].id),
    ).json()
    assert (edited["title"], edited["urgency"], edited["sector"]) == (
        "Novo titulo",
        "critica",
        "dp",
    )
    assert edited["due_date"] == "2026-11-30"
    assert edited["assignee"]["id"] == str(team["gestor"].id)

    cleared = patch(api_client, headers, demand, assignee_id=None, due_date=None).json()
    assert cleared["assignee"] is None
    assert cleared["due_date"] is None


def test_gestor_edits_what_he_sees_and_gets_404_for_the_rest(
    api_client,
    admin_conn,
    tenant_id,
    team,  # noqa: F811
):
    mine = new_demand(admin_conn, tenant_id, sector="fiscal")
    other = new_demand(admin_conn, tenant_id, sector="dp")
    headers = login_headers(api_client, team["gestor"])

    assert patch(api_client, headers, mine, urgency="alta").status_code == 200
    assert patch(api_client, headers, other, urgency="alta").status_code == 404


def test_gestor_cannot_move_a_demand_into_the_hr_sector(
    api_client,
    admin_conn,
    tenant_id,
    team,  # noqa: F811
):
    demand = new_demand(admin_conn, tenant_id, sector="fiscal")
    headers = login_headers(api_client, team["gestor"])

    assert patch(api_client, headers, demand, sector="rh-interno").status_code == 403


def test_colaborador_changes_only_the_status_of_his_own_demands(
    api_client,
    admin_conn,
    tenant_id,
    team,  # noqa: F811
):
    own = new_demand(admin_conn, tenant_id, assignee=team["colab"].id)
    unassigned = new_demand(admin_conn, tenant_id)
    headers = login_headers(api_client, team["colab"])

    assert patch(api_client, headers, own, status="em_andamento").json()["status"] == "em_andamento"
    for forbidden in (
        {"assignee_id": str(team["socio"].id)},
        {"urgency": "critica"},
        {"sector": "dp"},
        {"title": "outro"},
        {"due_date": "2026-12-01"},
    ):
        assert patch(api_client, headers, own, **forbidden).status_code == 403, forbidden
    assert patch(api_client, headers, unassigned, status="concluido").status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"status": "inventado"},
        {"urgency": "maxima"},
        {"due_date": "ontem"},
        {"title": ""},
        {"sector": "marketing"},
        {"id": "x"},
        {"closed_at": "2026-01-01"},
    ],
)
def test_patch_validates_input(api_client, admin_conn, tenant_id, team, body):  # noqa: F811
    demand = new_demand(admin_conn, tenant_id)
    headers = login_headers(api_client, team["socio"])

    assert patch(api_client, headers, demand, **body).status_code == 422


def test_assigning_an_hr_demand_to_someone_without_access_is_refused(
    api_client,
    admin_conn,
    tenant_id,
    team,  # noqa: F811
):
    demand = new_demand(admin_conn, tenant_id, sector="rh-interno")
    headers = login_headers(api_client, team["socio"])

    response = patch(api_client, headers, demand, assignee_id=str(team["colab"].id))

    assert response.status_code == 422


def test_subtasks_can_be_added_toggled_and_drive_the_progress(
    api_client,
    admin_conn,
    tenant_id,
    team,  # noqa: F811
):
    demand = new_demand(admin_conn, tenant_id)
    headers = login_headers(api_client, team["socio"])
    url = f"/api/v1/demands/{demand}/subtasks"

    first = api_client.post(url, json={"title": "Conferir valores"}, headers=headers)
    api_client.post(url, json={"title": "Emitir guia"}, headers=headers)
    assert first.status_code == 201

    toggled = api_client.patch(
        f"/api/v1/subtasks/{first.json()['id']}", json={"done": True}, headers=headers
    )
    assert toggled.status_code == 200
    assert toggled.json()["done"] is True

    detail = api_client.get(f"/api/v1/demands/{demand}", headers=headers).json()
    assert detail["progress"] == {"done": 1, "total": 2, "percent": 50}


def test_colaborador_works_the_subtasks_of_his_own_demand_only(
    api_client,
    admin_conn,
    tenant_id,
    team,  # noqa: F811
):
    own = new_demand(admin_conn, tenant_id, assignee=team["colab"].id)
    other = new_demand(admin_conn, tenant_id)
    headers = login_headers(api_client, team["colab"])

    mine = api_client.post(
        f"/api/v1/demands/{own}/subtasks", json={"title": "Passo"}, headers=headers
    )
    theirs = api_client.post(
        f"/api/v1/demands/{other}/subtasks", json={"title": "Passo"}, headers=headers
    )

    assert mine.status_code == 201
    assert theirs.status_code == 404


def _make_subtask(conn, tenant_id, demand_id):
    return conn.execute(
        "INSERT INTO subtasks (tenant_id, demand_id, title) VALUES (%s, %s, 'x') RETURNING id",
        (tenant_id, demand_id),
    ).fetchone()[0]


def test_subtasks_of_hidden_or_foreign_demands_do_not_exist_for_the_caller(
    api_client,
    admin_conn,
    tenant_id,
    other_channel,
    team,  # noqa: F811
):
    foreign_demand = new_demand(admin_conn, other_channel.tenant_id)
    foreign_subtask = _make_subtask(admin_conn, other_channel.tenant_id, foreign_demand)
    hidden = new_demand(admin_conn, tenant_id, sector="dp")
    hidden_subtask = _make_subtask(admin_conn, tenant_id, hidden)
    headers = login_headers(api_client, team["gestor"])

    for subtask in (foreign_subtask, hidden_subtask):
        url = f"/api/v1/subtasks/{subtask}"
        assert api_client.patch(url, json={"done": True}, headers=headers).status_code == 404
    url = f"/api/v1/demands/{foreign_demand}/subtasks"
    assert api_client.post(url, json={"title": "x"}, headers=headers).status_code == 404


def test_subtask_input_is_validated_and_capped(
    api_client,
    admin_conn,
    tenant_id,
    team,  # noqa: F811
):
    demand = new_demand(admin_conn, tenant_id)
    headers = login_headers(api_client, team["socio"])
    url = f"/api/v1/demands/{demand}/subtasks"

    assert api_client.post(url, json={"title": ""}, headers=headers).status_code == 422
    assert api_client.post(url, json={"title": "x" * 201}, headers=headers).status_code == 422
    for index in range(50):
        created = api_client.post(url, json={"title": f"passo {index}"}, headers=headers)
        assert created.status_code == 201
    assert api_client.post(url, json={"title": "passo 51"}, headers=headers).status_code == 409
    subtask = api_client.get(f"/api/v1/demands/{demand}", headers=headers).json()["subtasks"][0]
    empty = api_client.patch(f"/api/v1/subtasks/{subtask['id']}", json={}, headers=headers)
    assert empty.status_code == 422


def test_writes_require_authentication(api_client, admin_conn, tenant_id):
    demand = new_demand(admin_conn, tenant_id)

    created = api_client.post("/api/v1/demands", json={"title": "x", "sector": "fiscal"})
    patched = api_client.patch(f"/api/v1/demands/{demand}", json={"status": "novo"})
    subtask = api_client.post(f"/api/v1/demands/{demand}/subtasks", json={"title": "x"})

    assert (created.status_code, patched.status_code, subtask.status_code) == (401, 401, 401)


def _column(conn, demand_id, column):
    return conn.execute(f"SELECT {column} FROM demands WHERE id = %s", (demand_id,)).fetchone()[0]


def test_gestor_cannot_move_a_demand_to_a_sector_he_does_not_manage(
    api_client,
    admin_conn,
    tenant_id,
    team,  # noqa: F811
):
    demand = new_demand(admin_conn, tenant_id, sector="fiscal")
    headers = login_headers(api_client, team["gestor"])

    assert patch(api_client, headers, demand, sector="dp").status_code == 403
    assert _column(admin_conn, demand, "sector") == "fiscal"


def test_a_change_that_would_hide_the_demand_from_the_caller_is_rolled_back(
    api_client,
    admin_conn,
    tenant_id,
    team,  # noqa: F811
):
    demand = new_demand(admin_conn, tenant_id, sector="dp", assignee=team["gestor"].id)
    headers = login_headers(api_client, team["gestor"])

    response = patch(api_client, headers, demand, assignee_id=str(team["socio"].id))

    assert response.status_code == 403
    assert _column(admin_conn, demand, "assignee_id") == team["gestor"].id


@pytest.mark.parametrize("field", ["title", "urgency", "sector", "status"])
def test_null_is_rejected_for_required_fields(
    api_client,
    admin_conn,
    tenant_id,
    team,  # noqa: F811
    field,
):
    demand = new_demand(admin_conn, tenant_id)
    headers = login_headers(api_client, team["socio"])

    assert patch(api_client, headers, demand, **{field: None}).status_code == 422


def test_closing_an_already_closed_demand_keeps_the_original_closing_time(
    api_client,
    admin_conn,
    tenant_id,
    team,  # noqa: F811
):
    demand = new_demand(admin_conn, tenant_id, status="concluido")
    admin_conn.execute(
        "UPDATE demands SET closed_at = now() - interval '10 days' WHERE id = %s", (demand,)
    )
    before = _column(admin_conn, demand, "closed_at")

    patch(api_client, login_headers(api_client, team["socio"]), demand, status="concluido")

    assert _column(admin_conn, demand, "closed_at") == before


def test_subtask_null_values_are_rejected(api_client, admin_conn, tenant_id, team):  # noqa: F811
    demand = new_demand(admin_conn, tenant_id)
    subtask = admin_conn.execute(
        "INSERT INTO subtasks (tenant_id, demand_id, title) VALUES (%s, %s, 'x') RETURNING id",
        (tenant_id, demand),
    ).fetchone()[0]
    headers = login_headers(api_client, team["socio"])

    for body in ({"done": None}, {"title": None}):
        response = api_client.patch(f"/api/v1/subtasks/{subtask}", json=body, headers=headers)
        assert response.status_code == 422
