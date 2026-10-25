import pytest

from tests.conftest import login_headers


def new_demand(
    conn,
    tenant_id,
    *,
    sector="fiscal",
    status="novo",
    assignee=None,
    urgency="normal",
    title="Demanda de teste",
    contact_id=None,
    kind="tarefa",
    closed_days_ago=None,
):
    if status == "concluido" and closed_days_ago is not None:
        closed = f"now() - interval '{closed_days_ago} days'"
    elif status == "concluido":
        closed = "now()"
    else:
        closed = "NULL"
    return conn.execute(
        "INSERT INTO demands (tenant_id, contact_id, sector, kind, urgency, status, title, "
        f"assignee_id, closed_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, {closed}) RETURNING id",
        (tenant_id, contact_id, sector, kind, urgency, status, title, assignee),
    ).fetchone()[0]


@pytest.fixture
def team(tenant_id, make_user):
    return {
        "socio": make_user(tenant_id, "socio"),
        "gestor": make_user(tenant_id, "gestor", ["fiscal"]),
        "gestor_rh": make_user(tenant_id, "gestor", ["rh-interno"]),
        "colab": make_user(tenant_id, "colaborador", ["fiscal"]),
    }


def ids(response):
    assert response.status_code == 200, response.text
    return {item["id"] for item in response.json()}


def test_socio_sees_every_demand_of_the_tenant_and_nothing_from_others(
    api_client, admin_conn, tenant_id, other_channel, team
):
    mine = new_demand(admin_conn, tenant_id)
    new_demand(admin_conn, other_channel.tenant_id)

    response = api_client.get("/api/v1/demands", headers=login_headers(api_client, team["socio"]))

    assert ids(response) == {str(mine)}


def test_gestor_sees_his_sectors_plus_what_is_assigned_to_him(
    api_client, admin_conn, tenant_id, team
):
    own_sector = new_demand(admin_conn, tenant_id, sector="fiscal")
    assigned = new_demand(admin_conn, tenant_id, sector="dp", assignee=team["gestor"].id)
    new_demand(admin_conn, tenant_id, sector="dp")

    response = api_client.get("/api/v1/demands", headers=login_headers(api_client, team["gestor"]))

    assert ids(response) == {str(own_sector), str(assigned)}


def test_colaborador_sees_only_what_is_assigned_to_him(api_client, admin_conn, tenant_id, team):
    mine = new_demand(admin_conn, tenant_id, assignee=team["colab"].id)
    new_demand(admin_conn, tenant_id, sector="fiscal")

    response = api_client.get("/api/v1/demands", headers=login_headers(api_client, team["colab"]))

    assert ids(response) == {str(mine)}


def test_internal_hr_demands_are_restricted_to_socios_and_the_hr_sector(
    api_client, admin_conn, tenant_id, team
):
    hr = new_demand(admin_conn, tenant_id, sector="rh-interno", title="Pedido de folga")
    assigned_hr = new_demand(admin_conn, tenant_id, sector="rh-interno", assignee=team["colab"].id)

    cases = (("socio", True), ("gestor_rh", True), ("gestor", False), ("colab", False))
    for name, expected in cases:
        headers = login_headers(api_client, team[name])
        listed = ids(api_client.get("/api/v1/demands", headers=headers))
        assert (str(hr) in listed) is expected, name
        detail = api_client.get(f"/api/v1/demands/{hr}", headers=headers)
        assert detail.status_code == (200 if expected else 404), name

    # estar atribuido nao abre o RH interno para quem nao tem o setor
    colab_headers = login_headers(api_client, team["colab"])
    assert str(assigned_hr) not in ids(api_client.get("/api/v1/demands", headers=colab_headers))


def test_hidden_and_foreign_demands_look_like_they_do_not_exist(
    api_client, admin_conn, tenant_id, other_channel, team
):
    hidden = new_demand(admin_conn, tenant_id, sector="dp")
    foreign = new_demand(admin_conn, other_channel.tenant_id)
    gestor = login_headers(api_client, team["gestor"])
    socio = login_headers(api_client, team["socio"])

    assert api_client.get(f"/api/v1/demands/{hidden}", headers=gestor).status_code == 404
    assert api_client.get(f"/api/v1/demands/{foreign}", headers=gestor).status_code == 404
    assert api_client.get(f"/api/v1/demands/{foreign}", headers=socio).status_code == 404


def test_endpoints_require_authentication(api_client, admin_conn, tenant_id):
    demand = new_demand(admin_conn, tenant_id)

    for path in ("/api/v1/demands", f"/api/v1/demands/{demand}", "/api/v1/board"):
        assert api_client.get(path).status_code == 401


def test_list_filters_and_page_size_limit(api_client, admin_conn, tenant_id, team):
    new_demand(admin_conn, tenant_id, sector="fiscal", urgency="critica", title="A")
    new_demand(admin_conn, tenant_id, sector="dp", status="em_andamento", title="B")
    new_demand(admin_conn, tenant_id, sector="dp", assignee=team["socio"].id, title="C")
    headers = login_headers(api_client, team["socio"])

    def titles(query):
        response = api_client.get(f"/api/v1/demands?{query}", headers=headers)
        return sorted(item["title"] for item in response.json())

    assert titles("sector=dp") == ["B", "C"]
    assert titles("status=em_andamento") == ["B"]
    assert titles("urgency=critica") == ["A"]
    assert titles("assignee=me") == ["C"]
    assert titles("assignee=none") == ["A", "B"]
    assert titles(f"assignee={team['socio'].id}") == ["C"]
    assert len(api_client.get("/api/v1/demands?limit=1", headers=headers).json()) == 1
    assert api_client.get("/api/v1/demands?limit=1000", headers=headers).status_code == 422
    assert api_client.get("/api/v1/demands?status=inventado", headers=headers).status_code == 422
    assert api_client.get("/api/v1/demands?assignee=nao-e-uuid", headers=headers).status_code == 422


def test_board_groups_cards_by_status_with_counts_and_hides_old_closed_ones(
    api_client, admin_conn, tenant_id, team
):
    new_demand(admin_conn, tenant_id, status="novo", urgency="normal", title="Nova")
    new_demand(admin_conn, tenant_id, status="novo", urgency="critica", title="Nova critica")
    new_demand(admin_conn, tenant_id, status="aguardando", title="Esperando")
    new_demand(admin_conn, tenant_id, status="concluido", title="Fechada hoje")
    new_demand(
        admin_conn, tenant_id, status="concluido", closed_days_ago=30, title="Fechada faz tempo"
    )
    headers = login_headers(api_client, team["socio"])

    board = api_client.get("/api/v1/board", headers=headers).json()

    columns = {column["status"]: column for column in board["columns"]}
    assert [column["status"] for column in board["columns"]] == [
        "novo",
        "em_andamento",
        "aguardando",
        "concluido",
    ]
    assert columns["novo"]["count"] == 2
    assert [card["title"] for card in columns["novo"]["demands"]] == ["Nova critica", "Nova"]
    assert columns["em_andamento"]["count"] == 0
    assert [card["title"] for card in columns["concluido"]["demands"]] == ["Fechada hoje"]
    card = columns["novo"]["demands"][0]
    expected_fields = {
        "id",
        "title",
        "sector",
        "kind",
        "urgency",
        "status",
        "assignee",
        "contact",
        "progress",
        "idle_hours",
        "due_date",
    }
    assert expected_fields <= set(card)


def test_board_respects_visibility(api_client, admin_conn, tenant_id, team):
    new_demand(admin_conn, tenant_id, sector="dp", title="De outro setor")
    new_demand(admin_conn, tenant_id, sector="fiscal", title="Do meu setor")
    headers = login_headers(api_client, team["gestor"])

    board = api_client.get("/api/v1/board", headers=headers).json()

    all_titles = [card["title"] for column in board["columns"] for card in column["demands"]]
    assert all_titles == ["Do meu setor"]


def test_detail_shows_contact_assignee_messages_subtasks_and_progress(
    api_client, admin_conn, tenant_id, channel, team
):
    from tests.test_classification_store import add_message

    message_one = add_message(admin_conn, channel, "V1", "Preciso da guia", minutes=0)
    message_two = add_message(admin_conn, channel, "V2", "Segue o comprovante", minutes=5)
    contact_id = admin_conn.execute(
        "SELECT contact_id FROM messages WHERE id = %s", (message_one,)
    ).fetchone()[0]
    admin_conn.execute("UPDATE contacts SET name = 'Padaria' WHERE id = %s", (contact_id,))
    demand = new_demand(
        admin_conn, tenant_id, contact_id=contact_id, assignee=team["colab"].id, title="Guia do DAS"
    )
    for message in (message_two, message_one):
        admin_conn.execute(
            "INSERT INTO demand_messages (tenant_id, demand_id, message_id) VALUES (%s, %s, %s)",
            (tenant_id, demand, message),
        )
    for title, done in (("Conferir valores", True), ("Emitir guia", False)):
        admin_conn.execute(
            "INSERT INTO subtasks (tenant_id, demand_id, title, done) VALUES (%s, %s, %s, %s)",
            (tenant_id, demand, title, done),
        )

    response = api_client.get(
        f"/api/v1/demands/{demand}", headers=login_headers(api_client, team["socio"])
    )

    body = response.json()
    assert response.status_code == 200
    assert body["contact"]["name"] == "Padaria"
    assert body["assignee"]["id"] == str(team["colab"].id)
    assert [m["text"] for m in body["messages"]] == ["Preciso da guia", "Segue o comprovante"]
    assert sorted(s["title"] for s in body["subtasks"]) == ["Conferir valores", "Emitir guia"]
    assert body["progress"] == {"done": 1, "total": 2, "percent": 50}
    assert body["messages_count"] == 2
