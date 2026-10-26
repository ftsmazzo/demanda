from datetime import datetime
from uuid import uuid4

from app.cases.contract import CaseDecision
from app.classification.store import classify_pending
from tests.test_classification_service import FakeLLM, llm_output
from tests.test_classification_store import add_message

CLASSIFIER = FakeLLM(llm_output(sector="contabil", kind="tarefa"))


def decision(**overrides):
    data = {
        "action": "new",
        "case_ref": None,
        "confidence": 0.9,
        "kind": "nota",
        "sector": "rh-interno",
        "urgency": "normal",
        "title": "Pedido de ferias de Ana",
        "summary": "A funcionaria Ana pediu ferias para dezembro.",
        "next_step": "Lancar as ferias no sistema de RH.",
        "when_phrase": None,
        "appointment_ref": None,
        "reason": "assunto novo",
    }
    data.update(overrides)
    return CaseDecision(**data)


class FakeCaseLLM:
    def __init__(self, *decisions, error=None):
        self.decisions = list(decisions)
        self.error = error
        self.calls = []

    def analyze(self, text, ctx):
        self.calls.append((text, ctx))
        if self.error:
            raise self.error
        return self.decisions.pop(0) if len(self.decisions) > 1 else self.decisions[0]


def phone():
    return "55119" + str(uuid4().int)[:8]


def say(conn, channel, database, text, *, who, minutes=0, message_id=None):
    """Mensagem recebida e ja classificada (a classificacao por mensagem e o primeiro filtro)."""
    message = add_message(
        conn, channel, message_id or uuid4().hex, text, phone=who, minutes=minutes
    )
    classify_pending(database, channel.tenant_id, llm=CLASSIFIER)
    return message


def demands_of(conn, tenant_id, marker):
    return conn.execute(
        "SELECT id, title, summary, next_step, kind, sector, urgency, needs_review, review_reason "
        "FROM demands WHERE tenant_id = %s AND (title LIKE %s OR summary LIKE %s) "
        "ORDER BY created_at",
        (tenant_id, f"%{marker}%", f"%{marker}%"),
    ).fetchall()


def events_of(conn, demand_id):
    return conn.execute(
        "SELECT actor, kind, data FROM case_events WHERE demand_id = %s ORDER BY created_at, id",
        (demand_id,),
    ).fetchall()


BASE = datetime(2026, 10, 20, 12, 0)  # so referencia; add_message soma minutos a partir daqui
