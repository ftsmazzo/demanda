"""Telas do dia a dia: Hoje (o que precisa de decisao) e Conversas (caixa de entrada)."""

from datetime import datetime, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.appointments import _SELECT as APPOINTMENT_SELECT
from app.api.appointments import _out as appointment_out
from app.api.deps import CurrentUserDep, get_db
from app.api.queries import CARD_SELECT, row_to_card
from app.api.schemas import AppointmentOut, Card, ContactRef
from app.core.access import can_access_hr, visibility_clause
from app.core.appointments import _tenant_zone
from app.db import Database

router = APIRouter(prefix="/api/v1")

DbDep = Annotated[Database, Depends(get_db)]
_MANAGERS = ("socio", "gestor")
LIST_LIMIT = 10
ATTENTION_IDLE_HOURS = 24

# mensagens recebidas que ja tem classificacao mas ainda nao viraram item (esperam a triagem)
_WAITING = """
    SELECT count(*) AS n FROM messages wm
    JOIN LATERAL (
        SELECT mc.action FROM message_classifications mc
        WHERE mc.message_id = wm.id ORDER BY mc.created_at DESC, mc.id DESC LIMIT 1
    ) wc ON true
    WHERE wc.action IN ('classified', 'attach_reply') {scope}
      AND NOT EXISTS (SELECT 1 FROM demand_messages wd WHERE wd.message_id = wm.id)
      AND NOT EXISTS (SELECT 1 FROM skipped_messages ws WHERE ws.message_id = wm.id)
"""


class ConversationSummary(BaseModel):
    contact: ContactRef
    last_text: str | None
    last_direction: str
    last_at: datetime
    open_items: int
    waiting: int


class Today(BaseModel):
    needs_review: list[Card]
    to_confirm: list[AppointmentOut]
    attention: list[Card]
    waiting_triage: int
    counts: dict[str, int]


_INBOX = """
    SELECT c.id, c.name, c.phone, c.kind, c.priority, lm.text, lm.direction, lm.ts,
           COALESCE(oi.n, 0), COALESCE(w.n, 0)
    FROM contacts c
    JOIN LATERAL (
        SELECT m.text, m.direction, m.provider_timestamp AS ts
        FROM messages m
        LEFT JOIN demand_messages dm ON dm.message_id = m.id
        LEFT JOIN demands d ON d.id = dm.demand_id
        WHERE m.contact_id = c.id AND (dm.demand_id IS NULL OR ({clause}))
        ORDER BY m.provider_timestamp DESC, m.id DESC LIMIT 1
    ) lm ON true
    LEFT JOIN LATERAL (
        SELECT count(*) AS n FROM demands d
        WHERE d.contact_id = c.id AND d.status <> 'concluido' AND ({clause})
    ) oi ON true
    LEFT JOIN LATERAL ({waiting}) w ON true
    WHERE (%s OR c.kind <> 'colaborador') {search} {only_waiting}
    ORDER BY lm.ts DESC, c.id LIMIT %s OFFSET %s
"""


def _like(text: str) -> str:
    bs = chr(92)
    escaped = text.replace(bs, bs * 2).replace("%", bs + "%").replace("_", bs + "_")
    return f"%{escaped}%"


@router.get("/conversations")
def list_conversations(
    user: CurrentUserDep,
    db: DbDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
    waiting: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ConversationSummary]:
    if user.role not in _MANAGERS:
        raise HTTPException(status_code=403, detail="sem permissao")
    clause, vis = visibility_clause(user)
    params: list = [*vis, *vis, can_access_hr(user)]
    search = ""
    if q and q.strip():
        search = "AND (c.name ILIKE %s OR c.phone LIKE %s)"
        params.extend([_like(q.strip()), _like(q.strip())])
    sql = _INBOX.format(
        clause=clause,
        waiting=_WAITING.format(scope="AND wm.contact_id = c.id"),
        search=search,
        only_waiting="AND COALESCE(w.n, 0) > 0" if waiting else "",
    )
    with db.tenant_transaction(user.tenant_id) as conn:
        rows = conn.execute(sql, [*params, limit, offset]).fetchall()
    return [
        ConversationSummary(
            contact=ContactRef(id=r[0], name=r[1], phone=r[2], kind=r[3], priority=r[4]),
            last_text=r[5],
            last_direction=r[6],
            last_at=r[7],
            open_items=r[8],
            waiting=r[9],
        )
        for r in rows
    ]


_IDLE = "FLOOR(EXTRACT(EPOCH FROM (now() - d.last_activity_at)) / 3600)"


@router.get("/today")
def today(user: CurrentUserDep, db: DbDep) -> Today:
    clause, vis = visibility_clause(user)
    manager = user.role in _MANAGERS
    with db.tenant_transaction(user.tenant_id) as conn:
        zone = _tenant_zone(conn, user.tenant_id)
        now = datetime.now(zone)
        start = datetime.combine(now.date(), time.min, tzinfo=zone)

        review = conn.execute(
            f"{CARD_SELECT} WHERE ({clause}) AND d.needs_review AND d.status <> 'concluido' "
            "ORDER BY d.last_activity_at DESC, d.id LIMIT %s",
            [*vis, LIST_LIMIT],
        ).fetchall()
        proposed = conn.execute(
            f"{APPOINTMENT_SELECT} WHERE ({clause}) AND a.status = 'proposed' "
            "AND a.starts_at >= now() - interval '24 hours' "
            "AND a.starts_at <= now() + interval '14 days' ORDER BY a.starts_at, a.id LIMIT %s",
            [*vis, LIST_LIMIT],
        ).fetchall()
        attention = conn.execute(
            f"{CARD_SELECT} WHERE ({clause}) AND d.status <> 'concluido' "
            f"AND {_IDLE} >= %s "
            "AND (d.urgency IN ('critica', 'alta') OR COALESCE(c.priority, false)) "
            "ORDER BY CASE d.urgency WHEN 'critica' THEN 3 WHEN 'alta' THEN 2 ELSE 1 END DESC, "
            "COALESCE(c.priority, false) DESC, d.last_activity_at, d.id LIMIT %s",
            [*vis, ATTENTION_IDLE_HOURS, LIST_LIMIT],
        ).fetchall()
        waiting = 0
        if manager:
            waiting = conn.execute(_WAITING.format(scope="")).fetchone()[0]
        open_total = conn.execute(
            f"SELECT count(*) FROM demands d WHERE ({clause}) AND d.status <> 'concluido'", vis
        ).fetchone()[0]
        meetings = conn.execute(
            f"SELECT count(*) FROM appointments a JOIN demands d ON d.id = a.demand_id "
            f"WHERE ({clause}) AND a.status <> 'cancelled' "
            "AND a.starts_at >= %s AND a.starts_at < %s",
            [*vis, start, start + timedelta(days=1)],
        ).fetchone()[0]
    return Today(
        needs_review=[row_to_card(r) for r in review],
        to_confirm=[appointment_out(r) for r in proposed],
        attention=[row_to_card(r) for r in attention],
        waiting_triage=waiting,
        counts={"open": open_total, "meetings_today": meetings},
    )
