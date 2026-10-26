"""Le mensagens pendentes, classifica e grava o resultado (uma transacao curta por etapa).

Limitacoes conhecidas (dependem de tabelas que ainda nao existem): o contexto nao traz o tipo do
contato, se ha demanda aberta nem o setor padrao do canal. Por isso respostas curtas ("ok") viram
ruido em vez de anexar a uma demanda, e a regra de RH interno ainda nao dispara em producao.
Rode uma execucao por vez: duas execucoes simultaneas pagariam a IA duas vezes pela mesma mensagem.
"""

import logging
from collections import Counter
from typing import Any
from uuid import UUID

from app.classification.domain import Classification, Context, Decision
from app.classification.llm import LLMClassifier
from app.classification.rules import RULES_VERSION
from app.classification.service import classify_message
from app.db import Database

logger = logging.getLogger(__name__)

RECENT_MESSAGES = 5
# falhas temporarias da IA nao viram classificacao definitiva: a mensagem fica pendente
# e a proxima execucao tenta de novo
_TRANSIENT_REASONS = {"llm_unavailable", "llm_error"}

_PENDING = """
    SELECT m.id, m.channel_id, m.contact_phone, m.text, (m.media IS NOT NULL),
           m.provider_timestamp, ct.kind,
           EXISTS (
               SELECT 1 FROM demands d
               WHERE d.contact_id = m.contact_id AND d.status <> 'concluido'
           ),
           EXISTS (
               SELECT 1 FROM agent_notifications an
               WHERE an.body <> '' AND btrim(an.body) = btrim(m.text)
           )
    FROM messages m LEFT JOIN contacts ct ON ct.id = m.contact_id
    WHERE m.direction = 'in'
      AND NOT EXISTS (
          SELECT 1 FROM message_classifications c
          WHERE c.message_id = m.id AND c.rules_version = %s
            AND (NOT %s OR c.reason IS DISTINCT FROM 'no_llm')
      )
    ORDER BY m.provider_timestamp, m.id
    LIMIT %s
"""

# Inclui as respostas enviadas pelo escritorio de proposito: dao contexto a conversa.
_RECENT = """
    SELECT text FROM messages
    WHERE tenant_id = %s AND channel_id = %s AND contact_phone = %s
      AND provider_timestamp < %s AND text IS NOT NULL
    ORDER BY provider_timestamp DESC
    LIMIT %s
"""

_INSERT = """
    INSERT INTO message_classifications (
        tenant_id, message_id, action, sector, kind, urgency, client_hint, confidence,
        source, needs_review, reason, model, rules_version
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (message_id, rules_version) WHERE reason IS DISTINCT FROM 'no_llm' DO NOTHING
"""


# O WhatsApp do escritorio tambem registra o que o agente manda aos socios (a conversa com o
# numero do agente esta no mesmo telefone). Sem este filtro, o aviso viraria um compromisso novo,
# que geraria outro aviso, e assim por diante.
_AGENT_ECHO = Decision(
    "noise",
    Classification("triagem", "ruido", "normal", None, 1.0, "rule", False, "agent_echo"),
)


def classify_pending(
    db: Database,
    tenant_id: UUID,
    *,
    llm: LLMClassifier | None = None,
    limit: int = 200,
) -> Counter[str]:
    """Classifica ate `limit` mensagens recebidas ainda sem classificacao (mais antigas primeiro).

    A leitura e a escrita ficam em transacoes curtas; a chamada de IA acontece fora delas.
    Uma mensagem que falhe ao gravar fica pendente (conta em "failed") e nao trava as demais.
    """
    with db.tenant_transaction(tenant_id) as conn:
        pending = conn.execute(_PENDING, (RULES_VERSION, llm is not None, limit)).fetchall()
        work = []
        for (
            message_id,
            channel_id,
            phone,
            text,
            has_media,
            sent_at,
            contact_kind,
            has_open,
            agent_echo,
        ) in pending:
            recent = conn.execute(
                _RECENT, (tenant_id, channel_id, phone, sent_at, RECENT_MESSAGES)
            ).fetchall()
            context = Context(
                contact_type=None if contact_kind == "desconhecido" else contact_kind,
                has_open_demand=has_open,
                has_media=has_media,
                recent=tuple(row[0] for row in reversed(recent)),
            )
            work.append((message_id, text or "", context, agent_echo))

    model = getattr(llm, "model", None)
    counts: Counter[str] = Counter()
    for message_id, text, context, agent_echo in work:
        decision = _AGENT_ECHO if agent_echo else classify_message(text, context, llm=llm)
        if decision.classification.reason in _TRANSIENT_REASONS:
            counts["deferred"] += 1
            continue
        try:
            with db.tenant_transaction(tenant_id) as conn:
                conn.execute(_INSERT, _row(tenant_id, message_id, decision, model))
        except Exception:
            logger.exception("falha ao gravar a classificacao da mensagem %s", message_id)
            counts["failed"] += 1
            continue
        counts[decision.action] += 1
    return counts


def _row(
    tenant_id: UUID, message_id: UUID, decision: Decision, model: str | None
) -> tuple[Any, ...]:
    c = decision.classification
    return (
        tenant_id,
        message_id,
        decision.action,
        c.sector,
        c.kind,
        c.urgency,
        c.client_hint,
        c.confidence,
        c.source,
        c.needs_review,
        c.reason,
        model if c.source == "llm" else None,
        RULES_VERSION,
    )
