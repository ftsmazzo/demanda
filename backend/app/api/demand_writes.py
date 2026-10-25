"""Escrita de demandas e subtarefas, com as regras de quem pode alterar o que."""

from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import CurrentUserDep, get_db
from app.api.queries import fetch_detail
from app.api.schemas import (
    DemandCreate,
    DemandPatch,
    Detail,
    SubtaskCreate,
    SubtaskOut,
    SubtaskPatch,
)
from app.core.access import HR_SECTOR, can_access_hr, can_create_in, visibility_clause
from app.db import Database

router = APIRouter(prefix="/api/v1")

MAX_SUBTASKS = 50
DbDep = Annotated[Database, Depends(get_db)]

# campo do corpo -> coluna (lista fechada: nenhum nome de coluna vem do cliente)
_EDITABLE = {"title": "title", "urgency": "urgency", "sector": "sector", "due_date": "due_date"}


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="demanda nao encontrada")


def _check_assignee(conn: psycopg.Connection, assignee_id: UUID | None, sector: str) -> None:
    """O responsavel precisa ser um usuario ativo do tenant e poder ver o setor da demanda."""
    if assignee_id is None:
        return
    row = conn.execute("SELECT role FROM users WHERE id = %s AND active", (assignee_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=422, detail="responsavel invalido")
    if sector == HR_SECTOR and row[0] != "socio":
        has_hr = conn.execute(
            "SELECT 1 FROM user_sectors WHERE user_id = %s AND sector = %s",
            (assignee_id, HR_SECTOR),
        ).fetchone()
        if has_hr is None:
            raise HTTPException(status_code=422, detail="responsavel sem acesso ao RH interno")


def _check_contact(conn: psycopg.Connection, contact_id: UUID | None) -> None:
    if contact_id is None:
        return
    if conn.execute("SELECT 1 FROM contacts WHERE id = %s", (contact_id,)).fetchone() is None:
        raise HTTPException(status_code=422, detail="contato invalido")


def _touch(conn: psycopg.Connection, demand_id: UUID) -> None:
    conn.execute(
        "UPDATE demands SET last_activity_at = now(), updated_at = now() WHERE id = %s",
        (demand_id,),
    )


@router.post("/demands", status_code=201)
def create_demand(body: DemandCreate, user: CurrentUserDep, db: DbDep) -> Detail:
    if not can_create_in(user, body.sector):
        raise HTTPException(status_code=403, detail="sem permissao para criar neste setor")
    with db.tenant_transaction(user.tenant_id) as conn:
        _check_assignee(conn, body.assignee_id, body.sector)
        _check_contact(conn, body.contact_id)
        demand_id = conn.execute(
            "INSERT INTO demands (tenant_id, contact_id, sector, kind, urgency, title, due_date, "
            "assignee_id, origin) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'manual') RETURNING id",
            (
                user.tenant_id,
                body.contact_id,
                body.sector,
                body.kind,
                body.urgency,
                body.title,
                body.due_date,
                body.assignee_id,
            ),
        ).fetchone()[0]
        detail = fetch_detail(conn, user, demand_id)
    return detail


@router.patch("/demands/{demand_id}")
def patch_demand(demand_id: UUID, body: DemandPatch, user: CurrentUserDep, db: DbDep) -> Detail:
    fields = body.model_fields_set
    clause, params = visibility_clause(user)
    with db.tenant_transaction(user.tenant_id) as conn:
        row = conn.execute(
            f"SELECT d.sector, d.assignee_id FROM demands d WHERE d.id = %s AND {clause} "
            "FOR UPDATE OF d",
            [demand_id, *params],
        ).fetchone()
        if row is None:
            raise _not_found()
        current_sector, current_assignee = row

        if user.role == "colaborador" and fields - {"status"}:
            raise HTTPException(status_code=403, detail="colaborador so altera o status")
        if body.sector == HR_SECTOR and not can_access_hr(user):
            raise HTTPException(status_code=403, detail="sem acesso ao RH interno")
        if "sector" in fields and not can_create_in(user, body.sector):
            raise HTTPException(status_code=403, detail="sem permissao para mover para este setor")

        sector = body.sector if "sector" in fields and body.sector else current_sector
        assignee = body.assignee_id if "assignee_id" in fields else current_assignee
        if "assignee_id" in fields or "sector" in fields:
            _check_assignee(conn, assignee, sector)

        sets, values = ["updated_at = now()", "last_activity_at = now()"], []
        for field, column in _EDITABLE.items():
            if field in fields:
                sets.append(f"{column} = %s")
                values.append(getattr(body, field))
        if "assignee_id" in fields:
            sets.append("assignee_id = %s")
            values.append(body.assignee_id)
        if "status" in fields and body.status:
            sets.append("status = %s")
            values.append(body.status)
            # reenviar "concluido" nao pode apagar a data real de conclusao
            sets.append(
                "closed_at = COALESCE(closed_at, now())"
                if body.status == "concluido"
                else "closed_at = NULL"
            )
        conn.execute(f"UPDATE demands SET {', '.join(sets)} WHERE id = %s", [*values, demand_id])
        detail = fetch_detail(conn, user, demand_id)
        if detail is None:
            # a alteracao tiraria a demanda da visao de quem a fez: desfaz tudo
            raise HTTPException(
                status_code=403, detail="a alteracao tiraria a demanda da sua visao"
            )
    return detail


@router.post("/demands/{demand_id}/subtasks", status_code=201)
def add_subtask(
    demand_id: UUID, body: SubtaskCreate, user: CurrentUserDep, db: DbDep
) -> SubtaskOut:
    clause, params = visibility_clause(user)
    with db.tenant_transaction(user.tenant_id) as conn:
        found = conn.execute(
            f"SELECT 1 FROM demands d WHERE d.id = %s AND {clause} FOR UPDATE OF d",
            [demand_id, *params],
        ).fetchone()
        if found is None:
            raise _not_found()
        total = conn.execute(
            "SELECT count(*) FROM subtasks WHERE demand_id = %s", (demand_id,)
        ).fetchone()[0]
        if total >= MAX_SUBTASKS:
            raise HTTPException(status_code=409, detail=f"limite de {MAX_SUBTASKS} subtarefas")
        row = conn.execute(
            "INSERT INTO subtasks (tenant_id, demand_id, title) VALUES (%s, %s, %s) "
            "RETURNING id, title, done",
            (user.tenant_id, demand_id, body.title),
        ).fetchone()
        _touch(conn, demand_id)
    return SubtaskOut(id=row[0], title=row[1], done=row[2])


@router.patch("/subtasks/{subtask_id}")
def patch_subtask(
    subtask_id: UUID, body: SubtaskPatch, user: CurrentUserDep, db: DbDep
) -> SubtaskOut:
    clause, params = visibility_clause(user)
    fields = body.model_fields_set
    with db.tenant_transaction(user.tenant_id) as conn:
        found = conn.execute(
            "SELECT s.demand_id FROM subtasks s JOIN demands d ON d.id = s.demand_id "
            f"WHERE s.id = %s AND {clause} FOR UPDATE OF s",
            [subtask_id, *params],
        ).fetchone()
        if found is None:
            raise HTTPException(status_code=404, detail="subtarefa nao encontrada")
        sets, values = [], []
        if "title" in fields and body.title is not None:
            sets.append("title = %s")
            values.append(body.title)
        if "done" in fields and body.done is not None:
            sets.append("done = %s")
            values.append(body.done)
        if not sets:
            raise HTTPException(status_code=422, detail="informe titulo ou done")
        row = conn.execute(
            f"UPDATE subtasks SET {', '.join(sets)} WHERE id = %s RETURNING id, title, done",
            [*values, subtask_id],
        ).fetchone()
        _touch(conn, found[0])
    return SubtaskOut(id=row[0], title=row[1], done=row[2])
