import time

import jwt
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.security.tokens import create_token, decode_token
from tests.conftest import JWT_SECRET, login_headers


def login(client, user, password=None, tenant=None, email=None):
    return client.post(
        "/api/v1/auth/login",
        json={
            "tenant": tenant or user.tenant_slug,
            "email": email or user.email,
            "password": password or user.password,
        },
    )


def test_login_returns_a_bearer_token_for_the_right_user(api_client, tenant_id, make_user):
    user = make_user(tenant_id, "gestor", ["fiscal"])

    response = login(api_client, user)

    body = response.json()
    assert response.status_code == 200
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    claims = decode_token(JWT_SECRET, body["access_token"])
    assert (claims.user_id, claims.tenant_id, claims.role) == (user.id, tenant_id, "gestor")
    assert "password" not in response.text


def test_login_ignores_email_case(api_client, tenant_id, make_user):
    user = make_user(tenant_id, email="Dono@Exemplo.com")

    assert login(api_client, user, email="dono@exemplo.COM").status_code == 200


def test_wrong_password_unknown_user_and_unknown_tenant_look_identical(
    api_client, tenant_id, make_user
):
    user = make_user(tenant_id)

    wrong_password = login(api_client, user, password="outra-senha-errada")
    unknown_user = login(api_client, user, email="ninguem@exemplo.com")
    unknown_tenant = login(api_client, user, tenant="nao-existe")

    for response in (wrong_password, unknown_user, unknown_tenant):
        assert response.status_code == 401
        assert response.json() == wrong_password.json()


def test_inactive_user_cannot_log_in(api_client, tenant_id, make_user):
    user = make_user(tenant_id, active=False)

    assert login(api_client, user).status_code == 401


def test_login_is_unavailable_without_a_configured_secret(admin_url, tenant_id, make_user):
    user = make_user(tenant_id)

    with TestClient(create_app(database_url=admin_url)) as no_secret_client:
        assert login(no_secret_client, user).status_code == 503


def test_repeated_failures_lock_the_account_for_a_while(api_client, tenant_id, make_user):
    user = make_user(tenant_id)
    other = make_user(tenant_id)

    for _ in range(5):
        assert login(api_client, user, password="senha-errada-123").status_code == 401

    blocked = login(api_client, user)
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert login(api_client, other).status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"tenant": "x", "email": "a@b.com"},
        {"tenant": "x", "email": "a@b.com", "password": "p" * 1000},
        {"tenant": "t" * 500, "email": "a@b.com", "password": "senha-qualquer-1"},
    ],
)
def test_login_rejects_malformed_or_oversized_input(api_client, body):
    assert api_client.post("/api/v1/auth/login", json=body).status_code == 422


def test_me_returns_the_profile_loaded_from_the_database(api_client, tenant_id, make_user):
    user = make_user(tenant_id, "gestor", ["fiscal", "dp"])
    headers = login_headers(api_client, user)

    response = api_client.get("/api/v1/me", headers=headers)

    body = response.json()
    assert response.status_code == 200
    assert (body["id"], body["role"], body["email"]) == (str(user.id), "gestor", user.email)
    assert sorted(body["sectors"]) == ["dp", "fiscal"]


def test_role_changes_in_the_database_apply_to_tokens_already_issued(
    api_client, admin_conn, tenant_id, make_user
):
    user = make_user(tenant_id, "socio")
    headers = login_headers(api_client, user)
    admin_conn.execute("UPDATE users SET role = 'colaborador' WHERE id = %s", (user.id,))

    assert api_client.get("/api/v1/me", headers=headers).json()["role"] == "colaborador"


def test_deactivating_a_user_kills_their_existing_tokens(
    api_client, admin_conn, tenant_id, make_user
):
    user = make_user(tenant_id)
    headers = login_headers(api_client, user)
    admin_conn.execute("UPDATE users SET active = false WHERE id = %s", (user.id,))

    assert api_client.get("/api/v1/me", headers=headers).status_code == 401


def test_requests_without_valid_credentials_are_unauthorized(api_client, tenant_id, make_user):
    user = make_user(tenant_id)
    expired = create_token(
        JWT_SECRET, user_id=user.id, tenant_id=tenant_id, role="socio", ttl_seconds=-5
    )
    foreign = create_token(
        "x" * 40, user_id=user.id, tenant_id=tenant_id, role="socio", ttl_seconds=60
    )
    none_alg = jwt.encode(
        {"sub": str(user.id), "tid": str(tenant_id), "role": "socio", "exp": int(time.time()) + 60},
        key="",
        algorithm="none",
    )

    assert api_client.get("/api/v1/me").status_code == 401
    assert api_client.get("/api/v1/me", headers={"Authorization": "Basic abc"}).status_code == 401
    for token in (expired, foreign, none_alg, "lixo"):
        response = api_client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401


def test_token_cannot_be_used_with_another_tenants_user_id(
    api_client, tenant_id, other_channel, make_user
):
    mine = make_user(tenant_id)
    forged = create_token(
        JWT_SECRET, user_id=mine.id, tenant_id=other_channel.tenant_id, role="socio", ttl_seconds=60
    )

    response = api_client.get("/api/v1/me", headers={"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401


def test_token_lifetime_must_be_sane(admin_url):
    for bad in (0, -1, 25 * 3600):
        with pytest.raises(ValueError):
            create_app(database_url=admin_url, jwt_secret=JWT_SECRET, token_ttl_seconds=bad)


def test_tokens_without_issuer_and_audience_are_rejected(api_client, tenant_id, make_user):
    user = make_user(tenant_id)
    bare = jwt.encode(
        {
            "sub": str(user.id),
            "tid": str(tenant_id),
            "role": "socio",
            "exp": int(time.time()) + 60,
        },
        JWT_SECRET,
        algorithm="HS256",
    )

    response = api_client.get("/api/v1/me", headers={"Authorization": f"Bearer {bare}"})

    assert response.status_code == 401


def test_login_attempts_are_capped_in_concurrency_to_protect_memory(
    api_client, tenant_id, make_user
):
    user = make_user(tenant_id)
    slots = api_client.app.state.auth.hash_slots
    held = [slots.acquire(blocking=False) for _ in range(10)]
    try:
        busy = login(api_client, user)
    finally:
        for acquired in held:
            if acquired:
                slots.release()

    assert busy.status_code == 503
    assert login(api_client, user).status_code == 200


def test_control_characters_from_the_client_never_reach_the_logs(
    api_client, tenant_id, make_user, caplog
):
    user = make_user(tenant_id)
    with caplog.at_level("WARNING"):
        login(api_client, user, password="errada-errada", tenant="falso\nlinha-forjada")

    assert "\n" not in "".join(record.getMessage() for record in caplog.records)
