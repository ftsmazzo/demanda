"""Consultas de demandas para a API. Todas recebem o usuario e aplicam a visibilidade."""

from typing import Any
from uuid import UUID

import psycopg

from app.api.schemas import (
    AppointmentBrief,
    Card,
    ContactRef,
    Detail,
    EventOut,
    MessageOut,
    PersonRef,
    Progress,
    SubtaskOut,
)
from app.core.access import visibility_clause
from app.core.users import CurrentUser

CARD_SELECT = """
    SELECT d.id, d.title, d.sector, d.kind, d.urgency, d.status, d.due_date, d.origin,
           d.created_at, d.last_activity_at, d.closed_at,
           d.assignee_id, u.name, d.contact_id, c.name, c.phone, c.kind,
           COALESCE(st.total, 0), COALESCE(st.done, 0), COALESCE(mc.total, 0),
           CASE WHEN d.status = 'concluido' THEN 0
                ELSE FLOOR(EXTRACT(EPOCH FROM (now() - d.last_activity_at)) / 3600)::int END,
           d.summary, d.next_step, d.needs_review, d.review_reason, COALESCE(c.priority, false)
    FROM demands d
    LEFT JOIN users u ON u.id = d.assignee_id
    LEFT JOIN contacts c ON c.id = d.contact_id
    LEFT JOIN LATERAL (
        SELECT count(*) AS total, count(*) FILTER (WHERE s.done) AS done
        FROM subtasks s WHERE s.demand_id = d.id
    ) st ON true
    LEFT JOIN LATERAL (
        SELECT count(*) AS total FROM demand_messages dm WHERE dm.demand_id = d.id
    ) mc ON true
"""

ORDER_BY = """
    ORDER BY CASE d.urgency WHEN 'critica' THEN 3 WHEN 'alta' THEN 2 ELSE 1 END DESC,
             COALESCE(c.priority, false) DESC, d.last_activity_at DESC, d.id
"""

_MESSAGES = """
    SELECT m.id, m.direction, m.text, m.message_type, m.provider_timestamp
    FROM demand_messages dm JOIN messages m ON m.id = dm.message_id
    WHERE dm.demand_id = %s
    ORDER BY m.provider_timestamp, m.id
    LIMIT 200
"""

_SUBTASKS = "SELECT id, title, done FROM subtasks WHERE demand_id = %s ORDER BY created_at, id"

_EVENTS = """
    SELECT id, actor, kind, data, created_at FROM case_events
    WHERE demand_id = %s ORDER BY created_at, id LIMIT 100
"""

_APPOINTMENTS = """
    SELECT id, title, starts_at, all_day, status FROM appointments
    WHERE demand_id = %s ORDER BY starts_at, id LIMIT 50
"""


def row_to_card(row: tuple[Any, ...]) -> Card:
    (
        did,
        title,
        sector,
        kind,
        urgency,
        status,
        due,
        origin,
        created,
        activity,
        closed,
        assignee_id,
        assignee_name,
        contact_id,
        contact_name,
        phone,
        contact_kind,
        total,
        done,
        messages,
        idle,
        summary,
        next_step,
        needs_review,
        review_reason,
        priority,
    ) = row
    percent = round(100 * done / total) if total else 0
    return Card(
        id=did,
        title=title,
        sector=sector,
        kind=kind,
        urgency=urgency,
        status=status,
        due_date=due,
        origin=origin,
        assignee=PersonRef(id=assignee_id, name=assignee_name) if assignee_id else None,
        contact=ContactRef(
            id=contact_id, name=contact_name, phone=phone, kind=contact_kind, priority=priority
        )
        if contact_id
        else None,
        progress=Progress(done=done, total=total, percent=percent),
        messages_count=messages,
        created_at=created,
        last_activity_at=activity,
        closed_at=closed,
        idle_hours=idle,
        summary=summary,
        next_step=next_step,
        needs_review=needs_review,
        review_reason=review_reason,
    )


def filters(
    user: CurrentUser, *, status=None, sector=None, urgency=None, assignee=None, priority=None
):
    """WHERE + parametros: visibilidade do usuario mais os filtros opcionais."""
    clause, params = visibility_clause(user)
    parts = [clause]
    if status:
        parts.append("d.status = %s")
        params.append(status)
    if sector:
        parts.append("d.sector = %s")
        params.append(sector)
    if urgency:
        parts.append("d.urgency = %s")
        params.append(urgency)
    if priority:
        parts.append(
            "EXISTS (SELECT 1 FROM contacts pc WHERE pc.id = d.contact_id AND pc.priority)"
        )
    if assignee == "none":
        parts.append("d.assignee_id IS NULL")
    elif assignee is not None:
        parts.append("d.assignee_id = %s")
        params.append(user.id if assignee == "me" else assignee)
    return " AND ".join(f"({p})" for p in parts), params


def fetch_detail(conn: psycopg.Connection, user: CurrentUser, demand_id: UUID) -> Detail | None:
    where, params = filters(user)
    row = conn.execute(
        f"{CARD_SELECT} WHERE d.id = %s AND {where}", [demand_id, *params]
    ).fetchone()
    if row is None:
        return None
    card = row_to_card(row)
    messages = [
        MessageOut(id=m[0], direction=m[1], text=m[2], type=m[3], sent_at=m[4])
        for m in conn.execute(_MESSAGES, (demand_id,)).fetchall()
    ]
    subtasks = [
        SubtaskOut(id=s[0], title=s[1], done=s[2])
        for s in conn.execute(_SUBTASKS, (demand_id,)).fetchall()
    ]
    events = [
        EventOut(id=e[0], actor=e[1], kind=e[2], data=e[3], created_at=e[4])
        for e in conn.execute(_EVENTS, (demand_id,)).fetchall()
    ]
    appointments = [
        AppointmentBrief(id=a[0], title=a[1], starts_at=a[2], all_day=a[3], status=a[4])
        for a in conn.execute(_APPOINTMENTS, (demand_id,)).fetchall()
    ]
    return Detail(
        **card.model_dump(),
        messages=messages,
        subtasks=subtasks,
        events=events,
        appointments=appointments,
    )
