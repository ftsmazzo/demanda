"""Agenda: compromissos propostos a partir das mensagens, para o escritorio confirmar."""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import CurrentUserDep, get_db
from app.api.schemas import AppointmentOut, AppointmentPatch, AppointmentStatus, ContactRef
from app.core.access import visibility_clause
from app.db import Database

router = APIRouter(prefix="/api/v1")

DbDep = Annotated[Database, Depends(get_db)]

_SELECT = """
    SELECT a.id, a.title, a.starts_at, a.all_day, a.status, a.demand_id, d.sector,
           c.id, c.name, c.phone, c.kind
    FROM appointments a
    JOIN demands d ON d.id = a.demand_id
    LEFT JOIN contacts c ON c.id = a.contact_id
"""
_EDITABLE = {"title": "title", "starts_at": "starts_at", "all_day": "all_day", "status": "status"}


def _out(row: tuple) -> AppointmentOut:
    contact = ContactRef(id=row[7], name=row[8], phone=row[9], kind=row[10]) if row[7] else None
    return AppointmentOut(
        id=row[0],
        title=row[1],
        starts_at=row[2],
        all_day=row[3],
        status=row[4],
        demand_id=row[5],
        sector=row[6],
        contact=contact,
    )


@router.get("/appointments")
def list_appointments(
    user: CurrentUserDep,
    db: DbDep,
    status: AppointmentStatus | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[AppointmentOut]:
    clause, params = visibility_clause(user)
    where = [f"({clause})"]
    if status:
        where.append("a.status = %s")
        params.append(status)
    else:
        where.append("a.status <> 'cancelled'")
    # sem "since", mostra de hoje em diante (compromissos de dia inteiro de hoje ainda interessam)
    where.append("a.starts_at >= %s")
    params.append(since or datetime.now(UTC) - timedelta(hours=24))
    if until:
        where.append("a.starts_at <= %s")
        params.append(until)
    with db.tenant_transaction(user.tenant_id) as conn:
        rows = conn.execute(
            f"{_SELECT} WHERE {' AND '.join(where)} ORDER BY a.starts_at, a.id LIMIT %s",
            [*params, limit],
        ).fetchall()
    return [_out(row) for row in rows]


def _fetch(conn: psycopg.Connection, appointment_id: UUID) -> AppointmentOut:
    return _out(conn.execute(f"{_SELECT} WHERE a.id = %s", (appointment_id,)).fetchone())


@router.patch("/appointments/{appointment_id}")
def patch_appointment(
    appointment_id: UUID, body: AppointmentPatch, user: CurrentUserDep, db: DbDep
) -> AppointmentOut:
    clause, params = visibility_clause(user)
    with db.tenant_transaction(user.tenant_id) as conn:
        found = conn.execute(
            f"SELECT d.sector FROM appointments a JOIN demands d ON d.id = a.demand_id "
            f"WHERE a.id = %s AND ({clause}) FOR UPDATE OF a",
            [appointment_id, *params],
        ).fetchone()
        if found is None:
            raise HTTPException(status_code=404, detail="compromisso nao encontrado")
        if user.role == "colaborador":
            raise HTTPException(status_code=403, detail="sem permissao")
        sets, values = ["updated_at = now()"], []
        for field, column in _EDITABLE.items():
            if field in body.model_fields_set:
                sets.append(f"{column} = %s")
                values.append(getattr(body, field))
        conn.execute(
            f"UPDATE appointments SET {', '.join(sets)} WHERE id = %s", [*values, appointment_id]
        )
        return _fetch(conn, appointment_id)
