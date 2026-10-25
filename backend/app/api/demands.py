"""Leitura de demandas: lista, quadro (Kanban) e detalhe."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import CurrentUserDep, get_db
from app.api.queries import CARD_SELECT, ORDER_BY, fetch_detail, filters, row_to_card
from app.api.schemas import Board, Card, Column, Detail, Sector, Status, Urgency
from app.db import Database

router = APIRouter(prefix="/api/v1")

STATUSES = ("novo", "em_andamento", "aguardando", "concluido")
BOARD_COLUMN_LIMIT = 100

DbDep = Annotated[Database, Depends(get_db)]


def parse_assignee(value: str | None) -> str | None:
    """Aceita me, none ou um uuid; qualquer outra coisa e erro de validacao."""
    if value in (None, "me", "none"):
        return value
    try:
        return str(UUID(value))
    except ValueError:
        raise HTTPException(status_code=422, detail="assignee deve ser me, none ou um id") from None


@router.get("/demands")
def list_demands(
    user: CurrentUserDep,
    db: DbDep,
    status: Status | None = None,
    sector: Sector | None = None,
    urgency: Urgency | None = None,
    assignee: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Card]:
    where, params = filters(
        user, status=status, sector=sector, urgency=urgency, assignee=parse_assignee(assignee)
    )
    with db.tenant_transaction(user.tenant_id) as conn:
        rows = conn.execute(
            f"{CARD_SELECT} WHERE {where} {ORDER_BY} LIMIT %s OFFSET %s", [*params, limit, offset]
        ).fetchall()
    return [row_to_card(row) for row in rows]


@router.get("/board")
def board(
    user: CurrentUserDep,
    db: DbDep,
    sector: Sector | None = None,
    assignee: str | None = None,
    closed_days: Annotated[int, Query(ge=1, le=365)] = 14,
) -> Board:
    where, params = filters(user, sector=sector, assignee=parse_assignee(assignee))
    recent = "(d.status <> 'concluido' OR d.closed_at >= now() - make_interval(days => %s))"
    base = f"{where} AND {recent}"
    base_params = [*params, closed_days]
    columns = []
    with db.tenant_transaction(user.tenant_id) as conn:
        counts = dict(
            conn.execute(
                f"SELECT d.status, count(*) FROM demands d WHERE {base} GROUP BY d.status",
                base_params,
            ).fetchall()
        )
        for status in STATUSES:
            rows = conn.execute(
                f"{CARD_SELECT} WHERE {base} AND d.status = %s {ORDER_BY} LIMIT %s",
                [*base_params, status, BOARD_COLUMN_LIMIT],
            ).fetchall()
            columns.append(
                Column(
                    status=status,
                    count=counts.get(status, 0),
                    demands=[row_to_card(row) for row in rows],
                )
            )
    return Board(columns=columns)


@router.get("/demands/{demand_id}")
def demand_detail(demand_id: UUID, user: CurrentUserDep, db: DbDep) -> Detail:
    with db.tenant_transaction(user.tenant_id) as conn:
        detail = fetch_detail(conn, user, demand_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="demanda nao encontrada")
    return detail
