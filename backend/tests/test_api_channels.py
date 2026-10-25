from tests.conftest import login_headers


def set_health(admin_conn, channel, state, minutes_ago=0):
    admin_conn.execute(
        "UPDATE channels SET health_state = %s, health_checked_at = now(), "
        "health_changed_at = now() - make_interval(mins => %s) WHERE id = %s",
        (state, minutes_ago, channel.channel_id),
    )


def test_a_manager_sees_the_state_of_the_channels_of_the_tenant(
    api_client, admin_conn, tenant_id, channel, other_channel, make_user
):
    set_health(admin_conn, channel, "close", minutes_ago=90)
    set_health(admin_conn, other_channel, "open")
    socio = make_user(tenant_id, "socio")

    response = api_client.get("/api/v1/channels/health", headers=login_headers(api_client, socio))

    assert response.status_code == 200
    body = response.json()
    assert [item["name"] for item in body] == ["Principal"]
    assert body[0]["state"] == "close"
    assert body[0]["healthy"] is False
    assert body[0]["changed_at"] is not None
    assert set(body[0]) == {"id", "name", "state", "healthy", "changed_at", "checked_at"}


def test_an_open_channel_is_healthy_and_an_unchecked_one_is_not_alarming(
    api_client, admin_conn, tenant_id, channel, make_user
):
    gestor = make_user(tenant_id, "gestor", ["fiscal"])
    headers = login_headers(api_client, gestor)

    unchecked = api_client.get("/api/v1/channels/health", headers=headers).json()[0]
    set_health(admin_conn, channel, "open")
    open_state = api_client.get("/api/v1/channels/health", headers=headers).json()[0]

    assert unchecked["state"] is None and unchecked["healthy"] is True
    assert open_state["healthy"] is True


def test_a_collaborator_and_anonymous_visitors_are_refused(
    api_client, tenant_id, channel, make_user
):
    colab = make_user(tenant_id, "colaborador", ["fiscal"])

    assert api_client.get("/api/v1/channels/health").status_code == 401
    refused = api_client.get("/api/v1/channels/health", headers=login_headers(api_client, colab))
    assert refused.status_code == 403
