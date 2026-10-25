"""Dependencias compartilhadas das rotas: banco, configuracao de auth e usuario atual."""

import threading
from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.users import CurrentUser, load_user
from app.db import Database
from app.security.throttle import LoginThrottle
from app.security.tokens import MIN_SECRET_LENGTH, TokenError, decode_token

_bearer = HTTPBearer(auto_error=False)

MAX_CONCURRENT_HASHES = 4
MIN_TTL_SECONDS = 60
MAX_TTL_SECONDS = 24 * 3600


@dataclass
class AuthSettings:
    secret: str | None
    ttl_seconds: int
    throttle: LoginThrottle
    # limita quantos logins gastam argon2 (memoria e CPU) ao mesmo tempo
    hash_slots: threading.BoundedSemaphore = field(
        default_factory=lambda: threading.BoundedSemaphore(MAX_CONCURRENT_HASHES)
    )

    def __post_init__(self) -> None:
        if not MIN_TTL_SECONDS <= self.ttl_seconds <= MAX_TTL_SECONDS:
            raise ValueError("TOKEN_TTL_MINUTES deve ficar entre 1 e 1440")
        if self.secret is not None and len(self.secret) < MIN_SECRET_LENGTH:
            raise ValueError(f"JWT_SECRET precisa ter pelo menos {MIN_SECRET_LENGTH} caracteres")


def get_db(request: Request) -> Database:
    db: Database | None = request.app.state.db
    if db is None:
        raise HTTPException(status_code=503, detail="database unavailable")
    return db


def get_auth(request: Request) -> AuthSettings:
    return request.app.state.auth


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401, detail="nao autenticado", headers={"WWW-Authenticate": "Bearer"}
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Database, Depends(get_db)],
    auth: Annotated[AuthSettings, Depends(get_auth)],
) -> CurrentUser:
    if auth.secret is None:
        raise HTTPException(status_code=503, detail="autenticacao nao configurada")
    if credentials is None:
        raise _unauthorized()
    try:
        claims = decode_token(auth.secret, credentials.credentials)
    except TokenError:
        raise _unauthorized() from None
    with db.tenant_transaction(claims.tenant_id) as conn:
        user = load_user(conn, claims.tenant_id, claims.user_id)
    if user is None:
        raise _unauthorized()
    return user


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
