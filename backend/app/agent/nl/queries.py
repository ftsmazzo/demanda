"""Respostas de consulta: os numeros e as listas vem do SQL, o texto e montado aqui."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import psycopg

from app.agent.nl.contract import Intent
from app.agent.nl.lookup import find_contacts, find_users
from app.core.sectors import labels

LIST_LIMIT = 8
STUCK_HOURS = 24
SUMMARY_STUCK_HOURS = 72
_STATUS_LABEL = {
    "novo": "nova",
    "em_andamento": "em andamento",
    "aguardando": "aguardando",
    "concluido": "concluída",
}
_WEEKDAY = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")
_IDLE = "FLOOR(EXTRACT(EPOCH FROM (%s::timestamptz - d.last_activity_at)) / 3600)::int"


def _which(label: str, options: list[tuple[object, str]]) -> str:
    names = "\n".join(f"- {name}" for _, name in options[:5])
    return f"Qual {label}? Encontrei mais de um:\n{names}\nRepita o pedido com o nome completo."


def query_demands(conn: psycopg.Connection, intent: Intent, now: datetime, app_url: str) -> str:
    where, params, scope = [], [], []
    names = labels(conn)
    if intent.assignee_name:
        people = find_users(conn, intent.assignee_name)
        if not people:
            return f"Não encontrei ninguém chamado {intent.assignee_name}."
        if len(people) > 1:
            return _which("pessoa", people)
        where.append("d.assignee_id = %s")
        params.append(people[0][0])
        scope.append(f"de {people[0][1]}")
    if intent.contact_name:
        clients = find_contacts(conn, intent.contact_name)
        if not clients:
            return f"Não encontrei nenhum cliente chamado {intent.contact_name}."
        where.append("d.contact_id = ANY(%s)")
        params.append([cid for cid, _ in clients])
        scope.append(f"de {clients[0][1]}" if len(clients) == 1 else f"de {intent.contact_name}")
    if intent.sector:
        where.append("d.sector = %s")
        params.append(intent.sector)
        scope.append(f"em {names.get(intent.sector, intent.sector)}")
    if intent.priority_only:
        where.append(
            "EXISTS (SELECT 1 FROM contacts pc WHERE pc.id = d.contact_id AND pc.priority)"
        )
        scope.append("de clientes prioritários")
    status = intent.status_filter or "abertas"
    if status == "abertas":
        where.append("d.status <> 'concluido'")
    elif status == "paradas":
        where.append(f"d.status <> 'concluido' AND {_IDLE} >= {STUCK_HOURS}")
        params.append(now)
        scope.append(f"paradas há {STUCK_HOURS} h ou mais")
    else:
        where.append("d.status = %s")
        params.append(status)
        scope.append(f"({_STATUS_LABEL[status]})")
    clause = " AND ".join(where)
    count = conn.execute(f"SELECT count(*) FROM demands d WHERE {clause}", params).fetchone()[0]
    suffix = (" " + " ".join(scope)) if scope else ""
    if count == 0:
        return f"Nenhuma demanda encontrada{suffix}."
    rows = conn.execute(
        "SELECT d.title, d.sector, d.status, u.name FROM demands d "
        f"LEFT JOIN users u ON u.id = d.assignee_id WHERE {clause} "
        "ORDER BY CASE d.urgency WHEN 'critica' THEN 3 WHEN 'alta' THEN 2 ELSE 1 END DESC, "
        "d.last_activity_at DESC, d.id LIMIT %s",
        [*params, LIST_LIMIT],
    ).fetchall()
    noun = "demanda" if count == 1 else "demandas"
    lines = [f"*{count} {noun}{suffix}*"]
    for title, sector, state, person in rows:
        who = f", {person}" if person and not intent.assignee_name else ""
        lines.append(f"- {title} ({names.get(sector, sector)}, {_STATUS_LABEL[state]}{who})")
    if count > len(rows):
        lines.append(f"...e mais {count - len(rows)}")
    lines.append(f"\nQuadro: {app_url.rstrip('/')}/")
    return "\n".join(lines)


def query_agenda(conn: psycopg.Connection, intent: Intent, zone: ZoneInfo, now: datetime) -> str:
    local = now.astimezone(zone)
    start = datetime.combine(local.date(), time.min, tzinfo=zone)
    span = {"today": 1, "tomorrow": 1, "week": 7}[intent.range or "today"]
    if intent.range == "tomorrow":
        start += timedelta(days=1)
    rows = conn.execute(
        "SELECT title, starts_at, all_day, status FROM appointments WHERE status <> 'cancelled' "
        "AND starts_at >= %s AND starts_at < %s ORDER BY starts_at, id",
        (start, start + timedelta(days=span)),
    ).fetchall()
    label = {"today": "hoje", "tomorrow": "amanhã", "week": "nos próximos 7 dias"}[
        intent.range or "today"
    ]
    if not rows:
        return f"Nenhum compromisso {label}."
    lines = [f"*Compromissos {label}*"]
    for title, starts_at, all_day, state in rows:
        at = starts_at.astimezone(zone)
        when = "dia todo" if all_day else at.strftime("%H:%M")
        day = f"{_WEEKDAY[at.weekday()]} {at:%d/%m} " if span > 1 else ""
        mark = " (a confirmar)" if state == "proposed" else ""
        lines.append(f"- {day}{when} {title}{mark}")
    return "\n".join(lines)


def summary(conn: psycopg.Connection, zone: ZoneInfo, now: datetime, app_url: str) -> str:
    local = now.astimezone(zone)
    start = datetime.combine(local.date(), time.min, tzinfo=zone)
    total, new, doing, waiting, critical, stuck, vip = conn.execute(
        "SELECT count(*), count(*) FILTER (WHERE d.status = 'novo'), "
        "count(*) FILTER (WHERE d.status = 'em_andamento'), "
        "count(*) FILTER (WHERE d.status = 'aguardando'), "
        "count(*) FILTER (WHERE d.urgency = 'critica'), "
        f"count(*) FILTER (WHERE {_IDLE} >= {SUMMARY_STUCK_HOURS}), "
        "count(*) FILTER (WHERE EXISTS (SELECT 1 FROM contacts pc WHERE pc.id = d.contact_id "
        "AND pc.priority)) FROM demands d WHERE d.status <> 'concluido'",
        (now,),
    ).fetchone()
    meetings = conn.execute(
        "SELECT count(*) FROM appointments WHERE status <> 'cancelled' "
        "AND starts_at >= %s AND starts_at < %s",
        (start, start + timedelta(days=7)),
    ).fetchone()[0]
    word = "aberta" if total == 1 else "abertas"
    crit = f"{critical} crítica" if critical == 1 else f"{critical} críticas"
    stuck_word = f"{stuck} parada" if stuck == 1 else f"{stuck} paradas"
    return (
        f"*Resumo agora*\n{total} {word} ({new} nova, {doing} em andamento, {waiting} aguardando)\n"
        f"{crit}, {stuck_word} há {SUMMARY_STUCK_HOURS // 24} dias ou mais, "
        f"{vip} de clientes prioritários\nCompromissos nos próximos 7 dias: {meetings}\n\n"
        f"Quadro: {app_url.rstrip('/')}/"
    )
