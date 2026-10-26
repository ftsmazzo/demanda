"""O que a IA devolve ao entender o pedido do socio. Validado de forma estrita."""

from dataclasses import dataclass, replace
from typing import Any

from app.classification.domain import SECTORS, URGENCIES

INTENTS = (
    "query_demands",
    "query_agenda",
    "summary",
    "create_task",
    "assign",
    "set_status",
    "mark_priority",
    "reschedule",
    "draft_message",
    "unknown",
)
STATUSES = ("novo", "em_andamento", "aguardando", "concluido")
STATUS_FILTERS = (*STATUSES, "abertas", "paradas")
RANGES = ("today", "tomorrow", "week")

MAX_TITLE = 120
MAX_NAME = 80
MAX_CASE_TEXT = 120
MAX_PHRASE = 80

# Os provedores recusam enum com null e booleano anulavel: "none" faz o papel de vazio.
NONE = "none"
_NULLABLE = {"type": ["string", "null"]}
OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": list(INTENTS)},
        "confidence": {"type": "number"},
        "title": _NULLABLE,
        "sector": {"type": "string", "enum": [*SECTORS, NONE]},
        "assignee_name": _NULLABLE,
        "contact_name": _NULLABLE,
        "urgency": {"type": "string", "enum": [*URGENCIES, NONE]},
        "due_phrase": _NULLABLE,
        "case_text": _NULLABLE,
        "status": {"type": "string", "enum": [*STATUSES, NONE]},
        "status_filter": {"type": "string", "enum": [*STATUS_FILTERS, NONE]},
        "range": {"type": "string", "enum": [*RANGES, NONE]},
        "priority_only": {"type": "boolean"},
        "priority_value": {"type": "string", "enum": ["yes", "no", NONE]},
    },
    "required": [
        "intent",
        "confidence",
        "title",
        "sector",
        "assignee_name",
        "contact_name",
        "urgency",
        "due_phrase",
        "case_text",
        "status",
        "status_filter",
        "range",
        "priority_only",
        "priority_value",
    ],
    "additionalProperties": False,
}


@dataclass(frozen=True, slots=True)
class Intent:
    intent: str
    confidence: float
    title: str | None = None
    sector: str | None = None
    assignee_name: str | None = None
    contact_name: str | None = None
    urgency: str | None = None
    due_phrase: str | None = None
    case_text: str | None = None
    status: str | None = None
    status_filter: str | None = None
    range: str | None = None
    priority_only: bool = False
    priority_value: bool | None = None


def _text(data: dict[str, Any], key: str, limit: int) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} nao e texto")
    return " ".join(value.split())[:limit].rstrip() or None


def _choice(data: dict[str, Any], key: str, allowed: tuple[str, ...]) -> str | None:
    value = data.get(key)
    if value is None or value == NONE:
        return None
    if value not in allowed:
        raise ValueError(f"{key} invalido: {value!r}")
    return value


def _flag(data: dict[str, Any], key: str, *, nullable: bool) -> bool | None:
    value = data.get(key)
    if value is None or value == NONE:
        return None if nullable else False
    if nullable and value in ("yes", "no"):
        return value == "yes"
    if not isinstance(value, bool):
        raise ValueError(f"{key} nao e booleano")
    return value


def parse_intent(data: Any, sectors: tuple[str, ...] | None = None) -> Intent:
    if not isinstance(data, dict):
        raise ValueError("resposta da IA nao e um objeto")
    name = data.get("intent")
    if name not in INTENTS:
        raise ValueError(f"intencao invalida: {name!r}")
    confidence = data.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, int | float):
        raise ValueError("confianca nao numerica")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("confianca fora de 0..1")

    intent = Intent(
        intent=name,
        confidence=float(confidence),
        title=_text(data, "title", MAX_TITLE),
        sector=_choice(data, "sector", sectors or SECTORS),
        assignee_name=_text(data, "assignee_name", MAX_NAME),
        contact_name=_text(data, "contact_name", MAX_NAME),
        urgency=_choice(data, "urgency", URGENCIES),
        due_phrase=_text(data, "due_phrase", MAX_PHRASE),
        case_text=_text(data, "case_text", MAX_CASE_TEXT),
        status=_choice(data, "status", STATUSES),
        status_filter=_choice(data, "status_filter", STATUS_FILTERS),
        range=_choice(data, "range", RANGES),
        priority_only=bool(_flag(data, "priority_only", nullable=False)),
        priority_value=_flag(data, "priority_value", nullable=True),
    )
    required = {
        "create_task": (intent.title,),
        "assign": (intent.case_text, intent.assignee_name),
        "set_status": (intent.case_text, intent.status),
        "mark_priority": (intent.contact_name, intent.priority_value),
        "reschedule": (intent.case_text, intent.due_phrase),
        "draft_message": (intent.case_text, intent.assignee_name),
    }.get(name, ())
    if any(value is None for value in required):
        raise ValueError(f"faltam campos para {name}")
    if name == "query_agenda" and intent.range is None:
        return replace(intent, range="today")
    return intent
