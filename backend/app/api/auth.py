import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import AuthSettings, CurrentUserDep, get_auth, get_db
from app.db import Database
from app.security.passwords import DUMMY_HASH, verify_password
from app.security.tokens import create_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

_INVALID = "credenciais invalidas"


class LoginRequest(BaseModel):
    tenant: str = Field(min_length=1, max_length=64)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post("/auth/login")
def login(
    body: LoginRequest,
    db: Annotated[Database, Depends(get_db)],
    auth: Annotated[AuthSettings, Depends(get_auth)],
) -> TokenResponse:
    if auth.secret is None:
        raise HTTPException(status_code=503, detail="autenticacao nao configurada")

    key = (body.tenant.strip().lower(), body.email.strip().lower())
    if auth.throttle.is_blocked(key):
        logger.warning("login bloqueado por excesso de tentativas tenant=%r", key[0])
        raise HTTPException(
            status_code=429,
            detail="muitas tentativas, tente mais tarde",
            headers={"Retry-After": "600"},
        )

    if not auth.hash_slots.acquire(blocking=False):
        raise HTTPException(
            status_code=503,
            detail="servidor ocupado, tente novamente",
            headers={"Retry-After": "2"},
        )
    try:
        found = db.auth_user(body.tenant.strip(), body.email.strip())
        # verifica sempre (hash descartavel se o usuario nao existe) para nao diferenciar os casos
        password_ok = verify_password(found.password_hash if found else DUMMY_HASH, body.password)
    finally:
        auth.hash_slots.release()
    if found is None or not password_ok:
        auth.throttle.record_failure(key)
        logger.warning("login falhou tenant=%r", key[0])
        raise HTTPException(status_code=401, detail=_INVALID)

    auth.throttle.reset(key)
    token = create_token(
        auth.secret,
        user_id=found.user_id,
        tenant_id=found.tenant_id,
        role=found.role,
        ttl_seconds=auth.ttl_seconds,
    )
    return TokenResponse(access_token=token, expires_in=auth.ttl_seconds)


@router.get("/me")
def me(user: CurrentUserDep) -> dict[str, object]:
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "sectors": list(user.sectors),
    }
