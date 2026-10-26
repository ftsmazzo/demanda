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


def contact_with(conn, channel, message_id, text, phone, *, direction="in", minutes=0):
    message = add_message(
        conn, channel, message_id, text, phone=phone, direction=direction, minutes=minutes
    )
    sql = "SELECT contact_id FROM messages WHERE id = %s"
    return conn.execute(sql, (message,)).fetchone()[0], message


def link(conn, tenant_id, demand, message):
    conn.execute(
        "INSERT INTO demand_messages (tenant_id, demand_id, message_id) VALUES (%s, %s, %s)",
        (tenant_id, demand, message),
    )


def titles(board):
    return [card["title"] for column in board["columns"] for card in column["demands"]]


def test_the_board_leaves_meetings_to_the_agenda_unless_asked(
    api_client, admin_conn, tenant_id, team
):
    new_demand(admin_conn, tenant_id, kind="tarefa", title="Tarefa xyzfluxo")
    new_demand(admin_conn, tenant_id, kind="compromisso", title="Reuniao xyzfluxo")
    headers = login_headers(api_client, team["socio"])

    default = titles(api_client.get("/api/v1/board", headers=headers).json())
    with_meetings = titles(api_client.get("/api/v1/board?meetings=true", headers=headers).json())

    assert "Tarefa xyzfluxo" in default and "Reuniao xyzfluxo" not in default
    assert {"Tarefa xyzfluxo", "Reuniao xyzfluxo"} <= set(with_meetings)


def test_the_inbox_lists_contacts_by_latest_message_with_open_items(
    api_client, admin_conn, channel, team
):
    older, _ = contact_with(admin_conn, channel, "IN1", "antiga xyzcx", "5511900030001", minutes=0)
    newer, first = contact_with(
        admin_conn, channel, "IN2", "a guia xyzcx", "5511900030002", minutes=30
    )
    add_message(admin_conn, channel, "IN3", "e a folha xyzcx", phone="5511900030002", minutes=40)
    case = new_demand(admin_conn, channel.tenant_id, contact_id=newer, title="Guia")
    link(admin_conn, channel.tenant_id, case, first)
    headers = login_headers(api_client, team["gestor"])

    body = api_client.get("/api/v1/conversations", headers=headers).json()

    mine = [c for c in body if c["contact"]["id"] in (str(older), str(newer))]
    assert [c["contact"]["id"] for c in mine] == [str(newer), str(older)]
    top = mine[0]
    assert top["last_text"] == "e a folha xyzcx" and top["last_direction"] == "in"
    assert top["open_items"] == 1
    keys = {"contact", "last_text", "last_direction", "last_at", "open_items", "waiting"}
    assert keys <= set(top)


def test_messages_still_waiting_for_triage_are_counted(
    api_client, database, admin_conn, channel, team
):
    who, _ = contact_with(admin_conn, channel, "WT1", "preciso da guia xyzwait", "5511900030003")
    classify_pending(database, channel.tenant_id, llm=FakeLLM(llm_output()))
    headers = login_headers(api_client, team["socio"])

    body = api_client.get("/api/v1/conversations", headers=headers).json()

    row = next(c for c in body if c["contact"]["id"] == str(who))
    assert row["waiting"] == 1
    only = api_client.get("/api/v1/conversations?waiting=true", headers=headers).json()
    assert str(who) in [c["contact"]["id"] for c in only]


def test_search_filters_by_name_or_phone_and_priority_contacts_float_up(
    api_client, admin_conn, channel, team
):
    vip, _ = contact_with(admin_conn, channel, "SR1", "oi xyzbusca", "5511900030004", minutes=0)
    other, _ = contact_with(admin_conn, channel, "SR2", "ola xyzbusca", "5511900030005", minutes=50)
    admin_conn.execute(
        "UPDATE contacts SET name = 'Padaria Lua xyz', priority = true WHERE id = %s", (vip,)
    )
    headers = login_headers(api_client, team["socio"])

    found = api_client.get("/api/v1/conversations?q=padaria lua", headers=headers).json()
    assert [c["contact"]["id"] for c in found] == [str(vip)]
    assert found[0]["contact"]["priority"] is True
    assert (
        api_client.get("/api/v1/conversations?q=" + "x" * 101, headers=headers).status_code == 422
    )
    assert other  # o outro contato existe mas nao casa com a busca


def test_the_inbox_respects_roles_hr_contacts_and_hidden_cases(
    api_client, admin_conn, channel, other_channel, team
):
    staff, _ = contact_with(admin_conn, channel, "RS1", "pedido de ferias xyzrh", "5511900030006")
    admin_conn.execute("UPDATE contacts SET kind = 'colaborador' WHERE id = %s", (staff,))
    mixed, hidden_msg = contact_with(
        admin_conn, channel, "RS2", "assunto de pessoal xyzrh", "5511900030007"
    )
    hidden_case = new_demand(admin_conn, channel.tenant_id, contact_id=mixed, sector="dp")
    link(admin_conn, channel.tenant_id, hidden_case, hidden_msg)
    foreign, _ = contact_with(
        admin_conn, other_channel, "RS3", "de outro tenant xyzrh", "5511900030008"
    )

    def ids(who):
        response = api_client.get(
            "/api/v1/conversations", headers=login_headers(api_client, team[who])
        )
        return response, [
            c["contact"]["id"] for c in response.json()
        ] if response.status_code == 200 else []

    colab, _ = ids("colab")
    _, gestor_ids = ids("gestor")
    _, socio_ids = ids("socio")

    assert colab.status_code == 403
    assert str(staff) not in gestor_ids and str(staff) in socio_ids
    assert str(mixed) not in gestor_ids  # so tem mensagens de um caso que o gestor nao ve
    assert str(foreign) not in socio_ids
