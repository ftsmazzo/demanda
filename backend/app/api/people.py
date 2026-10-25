"""Contatos e usuarios (para corrigir contatos e escolher responsaveis)."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import CurrentUserDep, get_db
from app.api.schemas import ContactKind, ContactPatch, ContactRef, UserOut
from app.core.access import HR_SECTOR, can_access_hr
from app.core.users import CurrentUser
from app.db import Database

router = APIRouter(prefix="/api/v1")

DbDep = Annotated[Database, Depends(get_db)]
_MANAGERS = ("socio", "gestor")


def _require_manager(user: CurrentUser) -> None:
    if user.role not in _MANAGERS:
        raise HTTPException(status_code=403, detail="sem permissao")


_BACKSLASH = chr(92)


def _like_escape(text: str) -> str:
    """Escapa curingas (e a propria barra) para que a busca seja literal."""
    return (
        text.replace(_BACKSLASH, _BACKSLASH * 2)
        .replace("%", _BACKSLASH + "%")
        .replace("_", _BACKSLASH + "_")
    )


@router.get("/contacts")
def list_contacts(
    user: CurrentUserDep,
    db: DbDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
    kind: ContactKind | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ContactRef]:
    _require_manager(user)
    where, params = ["TRUE"], []
    if kind:
        where.append("kind = %s")
        params.append(kind)
    if q and q.strip():
        pattern = f"%{_like_escape(q.strip())}%"
        where.append("(name ILIKE %s OR phone LIKE %s)")
        params.extend([pattern, pattern])
    with db.tenant_transaction(user.tenant_id) as conn:
        rows = conn.execute(
            "SELECT id, name, phone, kind FROM contacts WHERE "
            + " AND ".join(where)
            + " ORDER BY updated_at DESC, id LIMIT %s OFFSET %s",
            [*params, limit, offset],
        ).fetchall()
    return [ContactRef(id=r[0], name=r[1], phone=r[2], kind=r[3]) for r in rows]


@router.patch("/contacts/{contact_id}")
def patch_contact(
    contact_id: UUID, body: ContactPatch, user: CurrentUserDep, db: DbDep
) -> ContactRef:
    _require_manager(user)
    sets, values = ["updated_at = now()"], []
    if "name" in body.model_fields_set and body.name is not None:
        sets.append("name = %s")
        values.append(body.name)
    if "kind" in body.model_fields_set and body.kind is not None:
        sets.append("kind = %s")
        values.append(body.kind)
    if len(sets) == 1:
        raise HTTPException(status_code=422, detail="informe nome ou tipo")
    with db.tenant_transaction(user.tenant_id) as conn:
        row = conn.execute(
            f"UPDATE contacts SET {', '.join(sets)} WHERE id = %s RETURNING id, name, phone, kind",
            [*values, contact_id],
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="contato nao encontrado")
    return ContactRef(id=row[0], name=row[1], phone=row[2], kind=row[3])


@router.get("/users")
def list_users(user: CurrentUserDep, db: DbDep) -> list[UserOut]:
    _require_manager(user)
    with db.tenant_transaction(user.tenant_id) as conn:
        rows = conn.execute(
            "SELECT u.id, u.name, u.role, "
            "COALESCE(array_agg(s.sector ORDER BY s.sector) FILTER (WHERE s.sector IS NOT NULL), "
            "'{}') FROM users u LEFT JOIN user_sectors s ON s.user_id = u.id "
            "WHERE u.active GROUP BY u.id ORDER BY u.name, u.id"
        ).fetchall()
    # quem esta no RH interno nao e exposto a quem nao tem acesso a esse setor
    show_hr = can_access_hr(user)
    return [
        UserOut(
            id=r[0],
            name=r[1],
            role=r[2],
            sectors=[s for s in r[3] if show_hr or s != HR_SECTOR],
        )
        for r in rows
    ]
