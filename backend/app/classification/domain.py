"""Tipos do dominio de classificacao de mensagens."""

from dataclasses import dataclass

SECTORS = (
    "triagem",
    "fiscal",
    "contabil",
    "dp",
    "societario",
    "financeiro",
    "rh-interno",
    "consultoria",
)
KINDS = ("tarefa", "compromisso", "duvida", "documento", "cobranca", "reclamacao")
STORED_KINDS = (*KINDS, "ruido", "indefinido")
URGENCIES = ("normal", "alta", "critica")
SOURCES = ("rule", "llm", "fallback")
ACTIONS = ("classified", "attach_reply", "noise")

_URGENCY_RANK = {name: rank for rank, name in enumerate(URGENCIES)}


def max_urgency(first: str, second: str) -> str:
    return first if _URGENCY_RANK[first] >= _URGENCY_RANK[second] else second


@dataclass(frozen=True, slots=True)
class Context:
    contact_type: str | None = None
    has_open_demand: bool = False
    has_media: bool = False
    channel_default_sector: str | None = None
    recent: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LLMOutput:
    sector: str
    kind: str
    urgency: str
    client_hint: str | None
    confidence: float
    is_noise: bool


@dataclass(frozen=True, slots=True)
class Classification:
    sector: str
    kind: str
    urgency: str
    client_hint: str | None
    confidence: float
    source: str
    needs_review: bool = False
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class Decision:
    action: str
    classification: Classification
