"""Setores do escritorio: listar (todos), criar e ajustar (so socio)."""

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from app.api.deps import CurrentUserDep, get_db
from app.core.access import HR_SECTOR, can_access_hr
from app.core.sectors import PALETTE, slugify
from app.db import Database

router = APIRouter(prefix="/api/v1")

DbDep = Annotated[Database, Depends(get_db)]
Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Color = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]
_COLUMNS = "slug, label, color, system, active"


class SectorOut(BaseModel):
    slug: str
    label: str
    color: str
    system: bool
    active: bool


class SectorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Label
    color: Color | None = None


class SectorPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: Label | None = None
    color: Color | None = None
    active: bool | None = None

    @model_validator(mode="after")
    def _something_to_change(self):
        if not self.model_fields_set:
            raise ValueError("informe pelo menos um campo")
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("os campos nao podem ser null")
        return self


def _out(row) -> SectorOut:
    return SectorOut(slug=row[0], label=row[1], color=row[2], system=row[3], active=row[4])


def _require_socio(user) -> None:
    if user.role != "socio":
        raise HTTPException(status_code=403, detail="so socio altera os setores")


def _same_label(conn: psycopg.Connection, label: str, *, except_slug: str | None = None) -> bool:
    wanted = slugify(label)
    return any(
        slugify(existing) == wanted
        for slug, existing in conn.execute("SELECT slug, label FROM sectors").fetchall()
        if slug != except_slug
    )


@router.get("/sectors")
def list_sectors(
    user: CurrentUserDep, db: DbDep, include_inactive: Annotated[bool, Query()] = False
) -> list[SectorOut]:
    where = "TRUE" if include_inactive else "active"
    with db.tenant_transaction(user.tenant_id) as conn:
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM sectors WHERE {where} "
            "ORDER BY slug <> 'triagem', created_at, slug"
        ).fetchall()
    show_hr = can_access_hr(user)
    return [_out(row) for row in rows if show_hr or row[0] != HR_SECTOR]


@router.post("/sectors", status_code=201)
def create_sector(body: SectorCreate, user: CurrentUserDep, db: DbDep) -> SectorOut:
    _require_socio(user)
    slug = slugify(body.label)
    if not slug:
        raise HTTPException(status_code=422, detail="o nome precisa ter letras ou numeros")
    with db.tenant_transaction(user.tenant_id) as conn:
        if _same_label(conn, body.label):
            raise HTTPException(status_code=409, detail="ja existe um setor com esse nome")
        taken = conn.execute("SELECT count(*) FROM sectors").fetchone()[0]
        row = conn.execute(
            "INSERT INTO sectors (tenant_id, slug, label, color) VALUES (%s, %s, %s, %s) "
            f"RETURNING {_COLUMNS}",
            (user.tenant_id, slug, body.label, body.color or PALETTE[taken % len(PALETTE)]),
        ).fetchone()
    return _out(row)


@router.patch("/sectors/{slug}")
def patch_sector(slug: str, body: SectorPatch, user: CurrentUserDep, db: DbDep) -> SectorOut:
    _require_socio(user)
    with db.tenant_transaction(user.tenant_id) as conn:
        current = conn.execute(
            f"SELECT {_COLUMNS} FROM sectors WHERE slug = %s FOR UPDATE", (slug,)
        ).fetchone()
        if current is None:
            raise HTTPException(status_code=404, detail="setor nao encontrado")
        if body.active is False and current[3]:
            raise HTTPException(status_code=409, detail="setor do sistema fica sempre ativo")
        if body.label is not None and _same_label(conn, body.label, except_slug=slug):
            raise HTTPException(status_code=409, detail="ja existe um setor com esse nome")
        row = conn.execute(
            "UPDATE sectors SET label = COALESCE(%s, label), color = COALESCE(%s, color), "
            f"active = COALESCE(%s, active) WHERE slug = %s RETURNING {_COLUMNS}",
            (body.label, body.color, body.active, slug),
        ).fetchone()
    return _out(row)
