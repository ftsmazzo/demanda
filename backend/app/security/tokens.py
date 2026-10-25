"""Tokens de acesso (JWT HS256) com expiracao curta."""

import time
from dataclasses import dataclass
from uuid import UUID

import jwt

ROLES = ("socio", "gestor", "colaborador")
MIN_SECRET_LENGTH = 32
ALGORITHM = "HS256"
ISSUER = "demanda"
AUDIENCE = "demanda-api"


class TokenError(Exception):
    """Token ausente, invalido, expirado ou com conteudo inesperado."""


@dataclass(frozen=True, slots=True)
class Claims:
    user_id: UUID
    tenant_id: UUID
    role: str


def _check_secret(secret: str) -> None:
    if len(secret) < MIN_SECRET_LENGTH:
        raise ValueError(f"o segredo do JWT precisa ter pelo menos {MIN_SECRET_LENGTH} caracteres")


def create_token(
    secret: str, *, user_id: UUID, tenant_id: UUID, role: str, ttl_seconds: int
) -> str:
    _check_secret(secret)
    now = int(time.time())
    payload = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": str(user_id),
        "tid": str(tenant_id),
        "role": role,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_token(secret: str, token: str) -> Claims:
    try:
        data = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={"require": ["exp", "sub", "tid", "role", "iss", "aud"]},
        )
        role = data["role"]
        if role not in ROLES:
            raise TokenError("papel desconhecido")
        return Claims(UUID(data["sub"]), UUID(data["tid"]), role)
    except TokenError:
        raise
    except (jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
        raise TokenError("token invalido") from exc
