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


def contact_of(conn, message_id):
    sql = "SELECT contact_id FROM messages WHERE id = %s"
    return conn.execute(sql, (message_id,)).fetchone()[0]


def link(conn, tenant_id, demand, message):
    conn.execute(
        "INSERT INTO demand_messages (tenant_id, demand_id, message_id) VALUES (%s, %s, %s)",
        (tenant_id, demand, message),
    )


def case_with_contact(conn, channel, message_id, text, *, phone, **kwargs):
    message = add_message(conn, channel, message_id, text, phone=phone)
    contact = contact_of(conn, message)
    demand = new_demand(conn, channel.tenant_id, contact_id=contact, **kwargs)
    link(conn, channel.tenant_id, demand, message)
    return demand, contact, message


def test_cards_and_detail_carry_the_ai_summary_next_step_review_flag_and_history(
    api_client, admin_conn, channel, team
):
    demand, _, message = case_with_contact(
        admin_conn, channel, "CA1", "Ana pediu ferias", phone="5511900010001", title="Ferias"
    )
    admin_conn.execute(
        "UPDATE demands SET summary = 'Ana pediu ferias em dezembro', next_step = 'Lancar', "
        "needs_review = true, review_reason = 'confirmar agrupamento' WHERE id = %s",
        (demand,),
    )
    admin_conn.execute(
        "INSERT INTO case_events (tenant_id, demand_id, message_id, actor, kind, data) "
        "VALUES (%s, %s, %s, 'ai', 'created', %s)",
        (channel.tenant_id, demand, message, '{"title": "Ferias"}'),
    )
    admin_conn.execute(
        "INSERT INTO appointments (tenant_id, demand_id, title, starts_at) "
        "VALUES (%s, %s, 'Reuniao', now() + interval '1 day')",
        (channel.tenant_id, demand),
    )
    headers = login_headers(api_client, team["socio"])

    detail = api_client.get(f"/api/v1/demands/{demand}", headers=headers).json()
    board = api_client.get("/api/v1/board", headers=headers).json()
    card = next(c for col in board["columns"] for c in col["demands"] if c["id"] == str(demand))

    assert detail["summary"] == "Ana pediu ferias em dezembro" and detail["next_step"] == "Lancar"
    assert detail["needs_review"] is True and detail["review_reason"] == "confirmar agrupamento"
    assert [e["kind"] for e in detail["events"]] == ["created"]
    assert detail["events"][0]["actor"] == "ai" and detail["events"][0]["data"]["title"] == "Ferias"
    assert [a["title"] for a in detail["appointments"]] == ["Reuniao"]
    assert card["summary"] == "Ana pediu ferias em dezembro" and card["needs_review"] is True


def test_a_manager_can_dismiss_the_review_flag_and_a_collaborator_cannot(
    api_client, admin_conn, channel, team
):
    demand, *_ = case_with_contact(
        admin_conn, channel, "CA2", "x", phone="5511900010002", assignee=team["colab"].id
    )
    admin_conn.execute(
        "UPDATE demands SET needs_review = true, review_reason = 'incerto' WHERE id = %s", (demand,)
    )
    url = f"/api/v1/demands/{demand}"
    colab = login_headers(api_client, team["colab"])
    gestor = login_headers(api_client, team["gestor"])

    refused = api_client.patch(url, json={"needs_review": False}, headers=colab)
    done = api_client.patch(url, json={"needs_review": False}, headers=gestor)

    assert refused.status_code == 403
    assert done.status_code == 200 and done.json()["needs_review"] is False
    assert done.json()["review_reason"] is None


def test_merge_moves_messages_appointments_and_history_into_the_target(
    api_client, admin_conn, channel, team
):
    target, contact, _ = case_with_contact(
        admin_conn, channel, "CM1", "alvo", phone="5511900010003", title="Alvo"
    )
    second = add_message(admin_conn, channel, "CM2", "origem", phone="5511900010003")
    source = new_demand(admin_conn, channel.tenant_id, contact_id=contact, title="Origem")
    link(admin_conn, channel.tenant_id, source, second)
    admin_conn.execute(
        "INSERT INTO appointments (tenant_id, demand_id, title, starts_at) "
        "VALUES (%s, %s, 'Reuniao', now() + interval '1 day')",
        (channel.tenant_id, source),
    )
    admin_conn.execute(
        "INSERT INTO case_events (tenant_id, demand_id, actor, kind) "
        "VALUES (%s, %s, 'ai', 'created')",
        (channel.tenant_id, source),
    )

    response = api_client.post(
        f"/api/v1/demands/{source}/merge",
        json={"into": str(target)},
        headers=login_headers(api_client, team["socio"]),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(target) and body["messages_count"] == 2
    assert [a["title"] for a in body["appointments"]] == ["Reuniao"]
    assert "merged" in [e["kind"] for e in body["events"]]
    sql = "SELECT count(*) FROM demands WHERE id = %s"
    assert admin_conn.execute(sql, (source,)).fetchone()[0] == 0


def test_merge_is_refused_for_other_contacts_hidden_cases_and_collaborators(
    api_client, admin_conn, channel, other_channel, team
):
    a, *_ = case_with_contact(admin_conn, channel, "CM3", "a", phone="5511900010004")
    b, *_ = case_with_contact(admin_conn, channel, "CM4", "b", phone="5511900010005")
    hidden, *_ = case_with_contact(
        admin_conn, channel, "CM5", "h", phone="5511900010006", sector="dp"
    )
    foreign = new_demand(admin_conn, other_channel.tenant_id)
    socio = login_headers(api_client, team["socio"])
    gestor = login_headers(api_client, team["gestor"])
    colab = login_headers(api_client, team["colab"])

    def merge(source, into, headers):
        url = f"/api/v1/demands/{source}/merge"
        return api_client.post(url, json={"into": str(into)}, headers=headers)

    assert merge(a, b, socio).status_code == 422  # contatos diferentes
    assert merge(a, a, socio).status_code == 422
    assert merge(hidden, a, gestor).status_code == 404
    assert merge(a, foreign, socio).status_code == 404
    assert merge(a, b, colab).status_code == 403


def test_the_conversation_of_a_contact_has_both_sides_the_cases_and_unlinked_messages(
    api_client, admin_conn, channel, team
):
    demand, contact, _ = case_with_contact(
        admin_conn, channel, "CC1", "Oi, preciso da guia", phone="5511900010007", title="Guia"
    )
    add_message(
        admin_conn, channel, "CC2", "Ja mando", phone="5511900010007", direction="out", minutes=1
    )
    add_message(admin_conn, channel, "CC3", "obrigado", phone="5511900010007", minutes=2)

    response = api_client.get(
        f"/api/v1/contacts/{contact}/conversation",
        headers=login_headers(api_client, team["gestor"]),
    )

    body = response.json()
    assert response.status_code == 200
    assert [m["text"] for m in body["messages"]] == ["Oi, preciso da guia", "Ja mando", "obrigado"]
    assert [m["direction"] for m in body["messages"]] == ["in", "out", "in"]
    assert body["messages"][0]["demand_id"] == str(demand)
    assert body["messages"][2]["demand_id"] is None
    assert [c["title"] for c in body["cases"]] == ["Guia"]
    assert body["contact"]["id"] == str(contact)


def test_the_conversation_is_for_managers_and_stays_inside_the_tenant(
    api_client, admin_conn, channel, other_channel, team
):
    _, contact, _ = case_with_contact(admin_conn, channel, "CC4", "x", phone="5511900010008")
    _, foreign, _ = case_with_contact(admin_conn, other_channel, "CC5", "y", phone="5511900010009")
    admin_conn.execute("UPDATE contacts SET kind = 'colaborador' WHERE id = %s", (contact,))

    def get(contact_id, who):
        url = f"/api/v1/contacts/{contact_id}/conversation"
        return api_client.get(url, headers=login_headers(api_client, team[who]))

    assert get(contact, "colab").status_code == 403
    assert get(foreign, "socio").status_code == 404
    assert get(contact, "gestor").status_code == 404  # conversa de funcionario do escritorio e RH
    assert get(contact, "socio").status_code == 200


def test_the_conversation_hides_messages_that_belong_to_cases_the_user_cannot_see(
    api_client, admin_conn, channel, team
):
    _, contact, _ = case_with_contact(
        admin_conn, channel, "CV1", "assunto fiscal", phone="5511900010010", sector="fiscal"
    )
    hidden_message = add_message(
        admin_conn, channel, "CV2", "assunto de pessoal", phone="5511900010010"
    )
    hidden_case = new_demand(admin_conn, channel.tenant_id, contact_id=contact, sector="dp")
    link(admin_conn, channel.tenant_id, hidden_case, hidden_message)
    url = f"/api/v1/contacts/{contact}/conversation"

    gestor = api_client.get(url, headers=login_headers(api_client, team["gestor"])).json()
    socio = api_client.get(url, headers=login_headers(api_client, team["socio"])).json()

    assert [m["text"] for m in gestor["messages"]] == ["assunto fiscal"]
    assert len(gestor["cases"]) == 1
    assert {m["text"] for m in socio["messages"]} == {"assunto fiscal", "assunto de pessoal"}
