from datetime import UTC, datetime, timedelta

from app.agent.runner import run_tenant
from app.agent.sender import SendError

URL = "https://demanda.exemplo.com"
# segunda-feira 26/10/2026, 18:30 em Sao Paulo
MON_EVENING = datetime(2026, 10, 26, 21, 30, tzinfo=UTC)
MON_MORNING = datetime(2026, 10, 26, 12, 5, tzinfo=UTC)  # 09:05 em Sao Paulo


class FakeSender:
    mode = "sent"

    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    def send(self, phone, text):
        if self.fail:
            raise SendError("falhou de proposito")
        self.sent.append((phone, text))


def cycle(database, tenant_id, sender, now):
    return run_tenant(database, tenant_id, sender, app_url=URL, now=now)


def add_recipient(conn, tenant_id, phone, *, name="Socio", active=True):
    return conn.execute(
        "INSERT INTO agent_recipients (tenant_id, name, phone, active) "
        "VALUES (%s, %s, %s, %s) RETURNING id",
        (tenant_id, name, phone, active),
    ).fetchone()[0]


def add_demand(
    conn,
    tenant_id,
    *,
    title="Demanda",
    status="novo",
    urgency="normal",
    sector="fiscal",
    created_at=None,
    idle_hours=0,
    now=MON_EVENING,
):
    created = created_at or now - timedelta(hours=idle_hours)
    last = now - timedelta(hours=idle_hours)
    closed = "%s" if status == "concluido" else "NULL"
    sql = (
        "INSERT INTO demands (tenant_id, sector, kind, urgency, status, title, created_at, "
        f"last_activity_at, closed_at) VALUES (%s, %s, 'tarefa', %s, %s, %s, %s, %s, {closed}) "
        "RETURNING id"
    )
    params = [tenant_id, sector, urgency, status, title, created, last]
    if status == "concluido":
        params.append(last)
    return conn.execute(sql, params).fetchone()[0]


def add_appointment(
    conn, tenant_id, demand_id, *, starts_at, created_at, status="proposed", title="Reuniao"
):
    return conn.execute(
        "INSERT INTO appointments (tenant_id, demand_id, title, starts_at, status, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
        (tenant_id, demand_id, title, starts_at, status, created_at),
    ).fetchone()[0]


def outbox(conn, tenant_id, kind=None):
    return conn.execute(
        "SELECT kind, status, attempts, body FROM agent_notifications "
        "WHERE tenant_id = %s AND (%s::text IS NULL OR kind = %s) ORDER BY created_at, id",
        (tenant_id, kind, kind),
    ).fetchall()
