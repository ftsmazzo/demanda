from uuid import uuid4

from app.agent.inbound import handle_inbound
from app.agent.nl.contract import Intent
from tests.agent_helpers import MON_MORNING, URL, FakeSender, add_demand, add_recipient


class FakeIntentLLM:
    def __init__(self, *intents, error=None):
        self.intents = list(intents)
        self.error = error
        self.calls = []

    def understand(self, text, ctx):
        self.calls.append((text, ctx))
        if self.error:
            raise self.error
        return self.intents.pop(0) if len(self.intents) > 1 else self.intents[0]


def intent(name="unknown", **fields):
    fields.setdefault("confidence", 0.9)
    return Intent(intent=name, **fields)


def named_user(make_user, conn, tenant_id, name, role="colaborador", sectors=("fiscal",)):
    user = make_user(tenant_id, role, list(sectors))
    conn.execute("UPDATE users SET name = %s WHERE id = %s", (name, user.id))
    return user


def contact(conn, tenant_id, name, *, priority=False):
    return conn.execute(
        "INSERT INTO contacts (tenant_id, phone, name, priority) VALUES (%s, %s, %s, %s) "
        "RETURNING id",
        (tenant_id, "55119" + str(uuid4().int)[:8], name, priority),
    ).fetchone()[0]


def demand(conn, tenant_id, title, *, assignee=None, contact_id=None, **kwargs):
    demand_id = add_demand(conn, tenant_id, title=title, **kwargs)
    conn.execute(
        "UPDATE demands SET assignee_id = %s, contact_id = %s WHERE id = %s",
        (assignee, contact_id, demand_id),
    )
    return demand_id


class Chat:
    """Uma conversa do socio com o agente: cada say() devolve a resposta recebida."""

    def __init__(self, database, conn, tenant_id, llm, *, phone=None):
        self.database, self.conn, self.tenant_id, self.llm = database, conn, tenant_id, llm
        self.sender = FakeSender()
        self.recipient = add_recipient(conn, tenant_id, phone or "55119" + str(uuid4().int)[:8])

    def say(self, text, *, now=MON_MORNING, cap=100):
        before = len(self.sender.sent)
        handle_inbound(
            self.database,
            self.sender,
            tenant_id=self.tenant_id,
            recipient_id=self.recipient,
            message_id=uuid4().hex,
            text=text,
            app_url=URL,
            now=now,
            intent_llm=self.llm,
            nl_daily_cap=cap,
        )
        return self.sender.sent[before][1] if len(self.sender.sent) > before else None
