import time
from uuid import uuid4

import jwt
import pytest

from app.security.passwords import hash_password, verify_password
from app.security.throttle import LoginThrottle
from app.security.tokens import TokenError, create_token, decode_token

SECRET = "segredo-de-teste-com-mais-de-32-bytes!!"


def test_password_hash_is_salted_and_verifiable():
    first = hash_password("uma-senha-bem-longa")
    second = hash_password("uma-senha-bem-longa")

    assert first != second
    assert verify_password(first, "uma-senha-bem-longa")
    assert not verify_password(first, "outra-senha-longa")


def test_verify_password_never_raises_on_garbage_hashes():
    assert verify_password("isto-nao-e-um-hash", "qualquer") is False
    assert verify_password("", "qualquer") is False


def test_short_passwords_are_refused():
    with pytest.raises(ValueError):
        hash_password("curta")


def test_token_roundtrip_carries_user_tenant_and_role():
    user_id, tenant_id = uuid4(), uuid4()

    token = create_token(
        SECRET, user_id=user_id, tenant_id=tenant_id, role="gestor", ttl_seconds=60
    )
    claims = decode_token(SECRET, token)

    assert (claims.user_id, claims.tenant_id, claims.role) == (user_id, tenant_id, "gestor")


def test_expired_token_is_rejected():
    token = create_token(SECRET, user_id=uuid4(), tenant_id=uuid4(), role="socio", ttl_seconds=-5)

    with pytest.raises(TokenError):
        decode_token(SECRET, token)


def test_token_signed_with_another_secret_is_rejected():
    token = create_token(
        "outro-segredo-" + "x" * 30,
        user_id=uuid4(),
        tenant_id=uuid4(),
        role="socio",
        ttl_seconds=60,
    )

    with pytest.raises(TokenError):
        decode_token(SECRET, token)


def test_token_with_alg_none_is_rejected():
    forged = jwt.encode(
        {"sub": str(uuid4()), "tid": str(uuid4()), "role": "socio", "exp": int(time.time()) + 60},
        key="",
        algorithm="none",
    )

    with pytest.raises(TokenError):
        decode_token(SECRET, forged)


def test_token_with_unknown_role_or_garbage_is_rejected():
    forged = jwt.encode(
        {"sub": str(uuid4()), "tid": str(uuid4()), "role": "deus", "exp": int(time.time()) + 60},
        SECRET,
        algorithm="HS256",
    )

    with pytest.raises(TokenError):
        decode_token(SECRET, forged)
    with pytest.raises(TokenError):
        decode_token(SECRET, "nao.e.um.token")


def test_short_secret_is_refused():
    with pytest.raises(ValueError):
        create_token("curto", user_id=uuid4(), tenant_id=uuid4(), role="socio", ttl_seconds=60)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_throttle_blocks_after_too_many_failures_and_recovers_with_time():
    clock = Clock()
    throttle = LoginThrottle(max_failures=3, window_seconds=60, clock=clock)
    key = ("tenant", "a@b.com")

    for _ in range(3):
        assert not throttle.is_blocked(key)
        throttle.record_failure(key)

    assert throttle.is_blocked(key)
    clock.now += 61
    assert not throttle.is_blocked(key)


def test_throttle_success_clears_failures_and_keys_are_independent():
    throttle = LoginThrottle(max_failures=2, window_seconds=60, clock=Clock())
    throttle.record_failure(("t", "a"))
    throttle.record_failure(("t", "a"))
    assert throttle.is_blocked(("t", "a"))
    assert not throttle.is_blocked(("t", "b"))

    throttle.reset(("t", "a"))

    assert not throttle.is_blocked(("t", "a"))


def test_throttle_does_not_grow_without_bound():
    throttle = LoginThrottle(max_failures=2, window_seconds=60, clock=Clock(), max_keys=10)

    for index in range(100):
        throttle.record_failure(("t", f"user{index}"))

    assert throttle.size() <= 10


def test_throttle_is_safe_under_concurrent_failures():
    from concurrent.futures import ThreadPoolExecutor

    throttle = LoginThrottle(max_failures=1000, window_seconds=60, clock=Clock())

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(
            pool.map(lambda _: [throttle.record_failure(("t", "a")) for _ in range(100)], range(8))
        )

    assert len(throttle._failures[("t", "a")]) == 800
