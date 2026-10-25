"""Saude dos canais de WhatsApp, para avisar na interface quando a escuta parou."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import CurrentUserDep, get_db
from app.db import Database

router = APIRouter(prefix="/api/v1")

DbDep = Annotated[Database, Depends(get_db)]
_MANAGERS = ("socio", "gestor")
# "open" esta bem; sem estado ainda (monitor nao rodou) ou "connecting" curto nao alarmam
_HEALTHY = (None, "open", "connecting")


class ChannelHealth(BaseModel):
    id: UUID
    name: str
    state: str | None
    healthy: bool
    changed_at: datetime | None
    checked_at: datetime | None


@router.get("/channels/health")
def channels_health(user: CurrentUserDep, db: DbDep) -> list[ChannelHealth]:
    if user.role not in _MANAGERS:
        raise HTTPException(status_code=403, detail="sem permissao")
    with db.tenant_transaction(user.tenant_id) as conn:
        rows = conn.execute(
            "SELECT id, name, health_state, health_changed_at, health_checked_at "
            "FROM channels WHERE active ORDER BY created_at, id"
        ).fetchall()
    return [
        ChannelHealth(
            id=r[0],
            name=r[1],
            state=r[2],
            healthy=r[2] in _HEALTHY,
            changed_at=r[3],
            checked_at=r[4],
        )
        for r in rows
    ]
