"""O que a IA de caso pode devolver, validado de forma estrita. Qualquer desvio vira ValueError."""

from dataclasses import dataclass
from typing import Any

from app.classification.domain import SECTORS, URGENCIES

ACTIONS = ("attach", "new", "ignore")
CASE_KINDS = ("tarefa", "compromisso", "duvida", "documento", "cobranca", "reclamacao", "nota")

MAX_TITLE = 120
MAX_SUMMARY = 400
MAX_NEXT_STEP = 200
MAX_PHRASE = 80
MAX_REASON = 200

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": list(ACTIONS)},
        "case_ref": {"type": ["integer", "null"]},
        "confidence": {"type": "number"},
        "kind": {"type": "string", "enum": list(CASE_KINDS)},
        "sector": {"type": "string", "enum": list(SECTORS)},
        "urgency": {"type": "string", "enum": list(URGENCIES)},
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "next_step": {"type": ["string", "null"]},
        "when_phrase": {"type": ["string", "null"]},
        "appointment_ref": {"type": ["integer", "null"]},
        "reason": {"type": "string"},
    },
    "required": [
        "action",
        "case_ref",
        "confidence",
        "kind",
        "sector",
        "urgency",
        "title",
        "summary",
        "next_step",
        "when_phrase",
        "appointment_ref",
        "reason",
    ],
    "additionalProperties": False,
}


@dataclass(frozen=True, slots=True)
class CaseDecision:
    action: str
    case_ref: int | None  # 1..n entre os casos abertos enviados
    confidence: float
    kind: str
    sector: str
    urgency: str
    title: str
    summary: str
    next_step: str | None
    when_phrase: str | None  # trecho da mensagem com dia/hora; quem calcula a data e o codigo
    appointment_ref: int | None  # 1..m entre os compromissos enviados
    reason: str


def _text(data: dict[str, Any], key: str, limit: int, *, required: bool) -> str | None:
    value = data.get(key)
    if value is None:
        if required:
            raise ValueError(f"campo ausente: {key}")
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} nao e texto")
    cleaned = " ".join(value.split())[:limit].rstrip()
    if required and not cleaned:
        raise ValueError(f"{key} vazio")
    return cleaned or None


def _ref(value: Any, limit: int, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= limit:
        raise ValueError(f"{name} invalido: {value!r}")
    return value


def _confidence(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("confianca nao numerica")
    if not 0.0 <= value <= 1.0:
        raise ValueError("confianca fora de 0..1")
    return float(value)


def parse_case_output(
    data: Any, *, open_cases: int, appointments: int, sectors: tuple[str, ...] | None = None
) -> CaseDecision:
    if not isinstance(data, dict):
        raise ValueError("resposta da IA nao e um objeto")
    action = data.get("action")
    if action not in ACTIONS:
        raise ValueError(f"acao invalida: {action!r}")
    confidence = _confidence(data.get("confidence"))
    reason = _text(data, "reason", MAX_REASON, required=False) or ""

    if action == "ignore":
        return CaseDecision(
            "ignore",
            None,
            confidence,
            "indefinido",
            "triagem",
            "normal",
            "",
            "",
            None,
            None,
            None,
            reason,
        )

    case_ref = data.get("case_ref")
    if action == "attach":
        case_ref = _ref(case_ref, open_cases, "case_ref")
        if case_ref is None:
            raise ValueError("attach exige case_ref")
    elif case_ref is not None:
        raise ValueError("new nao pode apontar para um caso")

    kind, sector, urgency = data.get("kind"), data.get("sector"), data.get("urgency")
    if kind not in CASE_KINDS:
        raise ValueError(f"tipo invalido: {kind!r}")
    if sector not in (sectors or SECTORS):
        raise ValueError(f"setor invalido: {sector!r}")
    if urgency not in URGENCIES:
        raise ValueError(f"urgencia invalida: {urgency!r}")

    return CaseDecision(
        action=action,
        case_ref=case_ref,
        confidence=confidence,
        kind=kind,
        sector=sector,
        urgency=urgency,
        title=_text(data, "title", MAX_TITLE, required=True) or "",
        summary=_text(data, "summary", MAX_SUMMARY, required=True) or "",
        next_step=_text(data, "next_step", MAX_NEXT_STEP, required=False),
        when_phrase=_text(data, "when_phrase", MAX_PHRASE, required=False),
        appointment_ref=_ref(data.get("appointment_ref"), appointments, "appointment_ref"),
        reason=reason,
    )
