"""Casos: uma chamada de IA por mensagem decide anexar, criar ou ignorar. O codigo aplica.

A IA so propoe. Qualquer falha, resposta fora do contrato ou teto de custo volta ao caminho
antigo por regras, que sempre cria algo visivel. Duvida nunca altera o que ja existe: vira caso
separado marcado para revisao. Contas de data e fuso sao feitas aqui, nunca pela IA.
"""

import logging
from collections import Counter
from dataclasses import replace
from datetime import date, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg
from psycopg.types.json import Jsonb

from app.agent.messages import when_text
from app.cases.contract import CaseDecision
from app.cases.llm import CaseLLM
from app.cases.prompt import AppointmentRef, CaseContext, OpenCase
from app.classification.domain import max_urgency
from app.core.appointments import _tenant_zone, insert_appointment
from app.core.demands import _materialize_one, lift_for_priority, materialize_demands
from app.core.schedule import When, extract_when
from app.db import Database

logger = logging.getLogger(__name__)

CONFIDENCE_MIN = 0.6  # abaixo disso a IA nao altera nada que ja existe
UPDATE_MIN = 0.8  # abaixo disso uma remarcacao vira so proposta
DEFAULT_DAILY_CAP = 400
MAX_OPEN_CASES = 5
MAX_APPOINTMENTS = 8
RECENT_PER_CASE = 3

_PENDING = """
    SELECT m.id, m.contact_id, m.text, m.provider_timestamp, c.action, c.sector, c.kind,
           c.urgency, ct.name, ct.kind
    FROM messages m
    JOIN contacts ct ON ct.id = m.contact_id
    JOIN LATERAL (
        SELECT mc.* FROM message_classifications mc
        WHERE mc.message_id = m.id ORDER BY mc.created_at DESC, mc.id DESC LIMIT 1
    ) c ON true
    WHERE c.action IN ('classified', 'attach_reply')
      AND NOT EXISTS (SELECT 1 FROM demand_messages dm WHERE dm.message_id = m.id)
      AND NOT EXISTS (SELECT 1 FROM skipped_messages sk WHERE sk.message_id = m.id)
    ORDER BY m.provider_timestamp, m.id
    LIMIT %s
"""

_OPEN_CASES = """
    SELECT id, title, COALESCE(summary, title), kind, sector FROM demands
    WHERE contact_id = %s AND status <> 'concluido'
    ORDER BY last_activity_at DESC, id DESC LIMIT %s
"""

_RECENT = """
    SELECT m.text FROM demand_messages dm JOIN messages m ON m.id = dm.message_id
    WHERE dm.demand_id = %s AND m.text IS NOT NULL
    ORDER BY m.provider_timestamp DESC, m.id DESC LIMIT %s
"""

_APPOINTMENTS = """
    SELECT id, demand_id, starts_at, all_day, status FROM appointments
    WHERE demand_id = ANY(%s) AND status <> 'cancelled'
    ORDER BY starts_at, id LIMIT %s
"""


def _event(
    conn: psycopg.Connection,
    tenant_id: UUID,
    demand_id: UUID,
    message_id: UUID | None,
    kind: str,
    data: dict[str, Any],
    actor: str = "ai",
) -> None:
    conn.execute(
        "INSERT INTO case_events (tenant_id, demand_id, message_id, actor, kind, data) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (tenant_id, demand_id, message_id, actor, kind, Jsonb(data)),
    )


def _reserve_call(conn: psycopg.Connection, tenant_id: UUID, day: date, cap: int) -> bool:
    """Conta uma chamada de IA no dia. Falso quando o teto do dia ja foi atingido."""
    row = conn.execute(
        "INSERT INTO ai_usage (tenant_id, day, purpose, calls) VALUES (%s, %s, 'case', 1) "
        "ON CONFLICT (tenant_id, day, purpose) DO UPDATE SET calls = ai_usage.calls + 1 "
        "WHERE ai_usage.calls < %s RETURNING calls",
        (tenant_id, day, cap),
    ).fetchone()
    return row is not None


def _build_context(
    conn: psycopg.Connection, row: tuple[Any, ...], zone: ZoneInfo
) -> tuple[CaseContext, list[UUID], list[UUID]]:
    """Contexto minimo para a IA, e os ids que os numeros [1..n] e [A1..Am] representam."""
    _, contact_id, _, sent_at, _, _, _, _, contact_name, contact_kind = row
    cases, case_ids = [], []
    for case_id, title, summary, kind, sector in conn.execute(
        _OPEN_CASES, (contact_id, MAX_OPEN_CASES)
    ).fetchall():
        recent = [r[0] for r in conn.execute(_RECENT, (case_id, RECENT_PER_CASE)).fetchall()]
        cases.append(OpenCase(case_id, title, summary, kind, sector, tuple(reversed(recent))))
        case_ids.append(case_id)
    appointments, appointment_ids = [], []
    if case_ids:
        for appt_id, demand_id, starts_at, all_day, status in conn.execute(
            _APPOINTMENTS, (case_ids, MAX_APPOINTMENTS)
        ).fetchall():
            label = when_text(starts_at.astimezone(zone), all_day)
            appointments.append(
                AppointmentRef(appt_id, case_ids.index(demand_id) + 1, label, status)
            )
            appointment_ids.append(appt_id)
    ctx = CaseContext(
        contact_name, contact_kind, sent_at.astimezone(zone), tuple(cases), tuple(appointments)
    )
    return ctx, case_ids, appointment_ids


def _local_when(decision: CaseDecision, text: str | None, local_now: datetime) -> When | None:
    if not decision.when_phrase:
        return None
    return extract_when(decision.when_phrase, local_now) or extract_when(text or "", local_now)


def _handled(conn: psycopg.Connection, message_id: UUID) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM demand_messages WHERE message_id = %s "
            "UNION ALL SELECT 1 FROM skipped_messages WHERE message_id = %s",
            (message_id, message_id),
        ).fetchone()
        is not None
    )


def _link(conn: psycopg.Connection, tenant_id: UUID, demand_id: UUID, message_id: UUID) -> None:
    conn.execute(
        "INSERT INTO demand_messages (tenant_id, demand_id, message_id) VALUES (%s, %s, %s)",
        (tenant_id, demand_id, message_id),
    )


def _attach(conn, tenant_id, case_id, existing, message_id, sent_at, d: CaseDecision) -> None:
    urgency, _, old_summary = existing
    _link(conn, tenant_id, case_id, message_id)
    conn.execute(
        "UPDATE demands SET summary = %s, next_step = %s, urgency = %s, "
        "sector = CASE WHEN sector = 'triagem' THEN %s ELSE sector END, "
        "title = CASE WHEN summary IS NULL THEN %s ELSE title END, "
        "last_activity_at = GREATEST(last_activity_at, %s), ai_updated_at = now(), "
        "updated_at = now() WHERE id = %s",
        (
            d.summary,
            d.next_step,
            max_urgency(urgency, d.urgency),
            d.sector,
            d.title,
            sent_at,
            case_id,
        ),
    )
    _event(
        conn,
        tenant_id,
        case_id,
        message_id,
        "attached",
        {
            "confidence": d.confidence,
            "reason": d.reason,
            "summary_before": old_summary,
            "summary_after": d.summary,
        },
    )


def _create(
    conn, tenant_id, contact_id, message_id, sent_at, d: CaseDecision, review: str | None, candidate
) -> UUID:
    demand_id = conn.execute(
        "INSERT INTO demands (tenant_id, contact_id, sector, kind, urgency, title, summary, "
        "next_step, needs_review, review_reason, last_activity_at, ai_updated_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now()) RETURNING id",
        (
            tenant_id,
            contact_id,
            d.sector,
            d.kind,
            d.urgency,
            d.title,
            d.summary,
            d.next_step,
            review is not None,
            review,
            sent_at,
        ),
    ).fetchone()[0]
    _link(conn, tenant_id, demand_id, message_id)
    _event(
        conn,
        tenant_id,
        demand_id,
        message_id,
        "created",
        {"confidence": d.confidence, "reason": d.reason, "title": d.title},
    )
    if review:
        data = {"reason": review, "candidate": str(candidate) if candidate else None}
        _event(conn, tenant_id, demand_id, message_id, "review", data)
    return demand_id


def _when_data(when: When) -> dict[str, Any]:
    return {"starts_at": when.start.isoformat(), "all_day": when.all_day}


def _appointment(conn, tenant_id, row, demand_id, d: CaseDecision, appointment_ids, when) -> str:
    message_id, contact_id = row[0], row[1]
    found = None
    if d.appointment_ref:
        found = conn.execute(
            "SELECT a.id, a.demand_id, a.starts_at, a.all_day, a.status FROM appointments a "
            "JOIN demands dd ON dd.id = a.demand_id WHERE a.id = %s AND dd.contact_id = %s "
            "AND a.status <> 'cancelled' FOR UPDATE OF a",
            (appointment_ids[d.appointment_ref - 1], contact_id),
        ).fetchone()
    if found is None:
        insert_appointment(
            conn,
            tenant_id=tenant_id,
            demand_id=demand_id,
            contact_id=contact_id,
            message_id=message_id,
            title=d.title,
            when=when,
        )
        _event(conn, tenant_id, demand_id, message_id, "appointment_created", _when_data(when))
        return "appointment_created"
    appt_id, appt_demand, starts_at, all_day, status = found
    before = {"starts_at": starts_at.isoformat(), "all_day": all_day, "status": status}
    if d.confidence >= UPDATE_MIN:
        conn.execute(
            "UPDATE appointments SET starts_at = %s, all_day = %s, status = 'proposed', "
            "updated_at = now() WHERE id = %s",
            (when.start, when.all_day, appt_id),
        )
        data = {"appointment_id": str(appt_id), "before": before, "after": _when_data(when)}
        _event(conn, tenant_id, appt_demand, message_id, "appointment_updated", data)
        return "appointment_updated"
    conn.execute(
        "UPDATE demands SET needs_review = true, review_reason = 'possivel remarcacao' "
        "WHERE id = %s",
        (appt_demand,),
    )
    data = {"appointment_id": str(appt_id), "before": before, "proposed": _when_data(when)}
    _event(conn, tenant_id, appt_demand, message_id, "proposal", data)
    return "proposal"


def _apply(conn, tenant_id, row, d: CaseDecision, ctx, case_ids, appointment_ids) -> list[str]:
    message_id, contact_id, text, sent_at = row[0], row[1], row[2], row[3]
    d = replace(d, urgency=lift_for_priority(conn, contact_id, d.urgency))
    if d.action == "ignore":
        if d.confidence < CONFIDENCE_MIN:
            _materialize_one(conn, tenant_id, row[:8])
            return ["fallback"]
        conn.execute(
            "INSERT INTO skipped_messages (tenant_id, message_id, reason) "
            "VALUES (%s, %s, 'ai_ignore') ON CONFLICT DO NOTHING",
            (tenant_id, message_id),
        )
        return ["ignored"]

    target, existing, review, candidate = None, None, None, None
    if d.action == "attach":
        candidate = case_ids[d.case_ref - 1]
        existing = conn.execute(
            "SELECT urgency, sector, summary FROM demands "
            "WHERE id = %s AND contact_id = %s AND status <> 'concluido' FOR UPDATE",
            (candidate, contact_id),
        ).fetchone()
        if existing is not None and d.confidence >= CONFIDENCE_MIN:
            target = candidate
        elif existing is not None:
            review = "confirmar agrupamento"
    if target is None and review is None and d.confidence < CONFIDENCE_MIN:
        review = "classificacao incerta"

    if target is not None:
        _attach(conn, tenant_id, target, existing, message_id, sent_at, d)
        demand_id, outcomes = target, ["attached"]
    else:
        demand_id = _create(conn, tenant_id, contact_id, message_id, sent_at, d, review, candidate)
        outcomes = ["review" if review else "created"]

    when = _local_when(d, text, ctx.now)
    if when is not None and d.kind == "compromisso":
        outcomes.append(_appointment(conn, tenant_id, row, demand_id, d, appointment_ids, when))
    return outcomes


def _rules(db: Database, tenant_id: UUID, row: tuple[Any, ...]) -> str:
    with db.tenant_transaction(tenant_id) as conn:
        return _materialize_one(conn, tenant_id, row[:8])


def _prepare(db: Database, tenant_id: UUID, row, daily_cap: int):
    """Le o contexto e reserva a chamada de IA. None: ja tratada ou sem verba (usar regras)."""
    with db.tenant_transaction(tenant_id) as conn:
        if _handled(conn, row[0]):
            return "already"
        zone = _tenant_zone(conn, tenant_id)
        if not _reserve_call(conn, tenant_id, datetime.now(zone).date(), daily_cap):
            return None
        return _build_context(conn, row, zone)


def _process(db: Database, tenant_id: UUID, llm: CaseLLM, row, daily_cap: int) -> list[str]:
    message_id, contact_id, text, _, action = row[:5]
    if action != "classified":
        return [_rules(db, tenant_id, row)]  # respostas curtas anexam por regra, sem IA
    prepared = _prepare(db, tenant_id, row, daily_cap)
    if prepared == "already":
        return ["already"]
    if prepared is None:
        _rules(db, tenant_id, row)
        return ["fallback"]
    ctx, case_ids, appointment_ids = prepared
    try:
        decision = llm.analyze(text or "", ctx)
    except Exception as exc:
        logger.warning("IA de caso falhou (%s): usando regras", type(exc).__name__)
        _rules(db, tenant_id, row)
        return ["fallback"]

    with db.tenant_transaction(tenant_id) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (str(contact_id),))
        if _handled(conn, message_id):
            return ["already"]
        return _apply(conn, tenant_id, row, decision, ctx, case_ids, appointment_ids)


def materialize_cases(
    db: Database,
    tenant_id: UUID,
    llm: CaseLLM | None,
    *,
    limit: int = 200,
    daily_cap: int = DEFAULT_DAILY_CAP,
) -> Counter[str]:
    """Transforma mensagens classificadas em casos (ou, sem IA, em demandas pelas regras)."""
    if llm is None:
        return materialize_demands(db, tenant_id, limit=limit)
    with db.tenant_transaction(tenant_id) as conn:
        pending = conn.execute(_PENDING, (limit,)).fetchall()
    counts: Counter[str] = Counter()
    for row in pending:
        try:
            outcomes = _process(db, tenant_id, llm, row, daily_cap)
        except Exception:
            logger.exception("falha ao processar a mensagem %s", row[0])
            counts["failed"] += 1
            continue
        counts.update(outcomes)
    return counts
