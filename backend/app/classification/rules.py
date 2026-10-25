"""Regras deterministicas (template contabilidade-v1): rodam antes da IA e sao baratas."""

import re
import unicodedata
from dataclasses import dataclass

from app.classification.domain import Context, max_urgency

RULES_VERSION = "contabilidade-v1.2"

# Palavras comuns (das, nota, simples, razao, licenca) ficam de fora de proposito:
# so entram em frases que deixam o sentido claro.
_SECTOR_KEYWORDS: dict[str, tuple[tuple[str, int], ...]] = {
    "fiscal": (
        (r"\b(nf|nfs|nfe|nfse|imposto|impostos|iss|icms|ipi|pis|cofins)\b", 1),
        (r"\b(guia|guias|sped|darf|dctf|irpf|irpj|mei|tributo|tributos|fisca(?:l|is))\b", 1),
        (r"\b(notas? fisca(?:l|is)|notas? de (entrada|saida)|emitir nota|nota da prefeitura)\b", 1),
        (r"\b(simples nacional|guia do simples|optante pelo simples|do simples)\b", 1),
        (
            r"\b(obrigacao acessoria|obrigacoes acessorias|"
            r"receita federal|da receita|pela receita)\b",
            1,
        ),
        (r"\b(guia do|guia de|pagar o|emitir o|vence o|vencimento do|valor do|do|o) das\b", 1),
    ),
    "dp": (
        (r"\b(folha|ferias|rescisao|admissao|demissao|holerite|contracheque|atestado)\b", 1),
        (r"\b(esocial|fgts|inss|decimo terceiro|13o salario|funcionarios?|prolabore)\b", 1),
        (r"\b(vale transporte)\b", 1),
        (r"\bfolha de pagamento\b", 1),
    ),
    "societario": (
        (r"\b(abertura|alvara|certidao|certidoes|filial|cnpj|junta comercial)\b", 1),
        (
            r"\b(alteracao contratual|contrato social|encerrar a empresa|"
            r"encerramento da empresa|baixa da empresa|baixa no cnpj)\b",
            1,
        ),
    ),
    "contabil": (
        (r"\b(balancete|conciliacao|dre|fechamento|balanco|lancamentos?)\b", 1),
        (r"\b(plano de contas|demonstracoes? contabeis?|livro razao)\b", 1),
    ),
    "financeiro": (
        (r"\b(boletos?|honorarios?|cobranca|pagamento|pagar|fornecedor|mensalidade)\b", 1),
        (r"\b(fatura|pix|inadimplencia)\b", 1),
    ),
}

_HR_INTERNAL = re.compile(
    r"\b(folga|folgas|afastamento|afastar|afastado|licenca medica|banco de horas|ferias|atestado)\b"
)
_DAS_UPPERCASE = re.compile(r"\bDAS\b")

_TIME = r"\d{1,2}\s?(h|horas|:\d{2})\b"
_WEEKDAY = r"\b(segunda|terca|quarta|quinta|sexta|sabado)\b"
_KIND_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "reclamacao",
        re.compile(
            r"\b(ja pedi|ninguem (me )?(responde|retorna)|absurdo|reclamacao|reclamar|"
            r"demora (demais|muito)|muita demora|nunca (me )?respondem|descaso|pessimo|"
            r"vou (trocar|cancelar) (de |o |a |os )?(contabilidade|escritorio|"
            r"contrato|servicos?))\b"
        ),
    ),
    (
        "compromisso",
        re.compile(
            r"\b(reuniao|agendar|marcar|marcamos|visita|videochamada)\b|"
            + _WEEKDAY
            + r".*\b"
            + _TIME
            + r"|\bas "
            + _TIME
        ),
    ),
    (
        "cobranca",
        re.compile(
            r"\b(boletos?|cobranca|honorarios?|fatura|mensalidade|pagar)\b"
            r"|(?<!folha de )\bpagamento\b"
        ),
    ),
    ("duvida", re.compile(r"\b(quero|queria|gostaria de|preciso|precisava) saber\b")),
    (
        "tarefa",
        re.compile(
            r"\b(preciso|precisa|precisamos|necessito|solicito|gostaria|quero|queria|favor|"
            r"vou precisar|vamos precisar|precisarei|nao consegui|nao consigo)\b|"
            r"\b(pode|podem|poderia|poderiam) (fazer|calcular|enviar|mandar|ver|emitir|gerar|"
            r"verificar|resolver|registrar|me enviar|me mandar)\b"
        ),
    ),
    (
        "duvida",
        re.compile(r"\b(quando|como|qual|quais|quanto|onde|porque|quem|posso|pode)\b|\?"),
    ),
)

_CRITICAL = re.compile(
    r"\bja pedi\b.*\b(\d+|duas|tres|varias|diversas) vezes\b|\bninguem (me )?responde\b|"
    r"\b(intimacao|multa|bloqueio|penhora)\b|\bvence hoje\b|\bprazo (acaba|vence|termina) hoje\b"
)
_HIGH = re.compile(
    r"\b(urgente|urgencia|o mais rapido|hoje|amanha cedo|atrasad[oa]|pra ontem|prioridade)\b"
)

_GREETING_TOKENS = {
    "bom",
    "boa",
    "dia",
    "tarde",
    "noite",
    "oi",
    "ola",
    "tudo",
    "bem",
    "e",
    "voce",
    "ai",
}
_ACK_TOKENS = {
    "ok",
    "certo",
    "show",
    "beleza",
    "fechado",
    "combinado",
    "sim",
    "pode",
    "ser",
    "otimo",
    "perfeito",
    "agradeco",
    "obrigado",
    "obrigada",
    "valeu",
    "vlw",
    "blz",
    "joia",
    "massa",
    "tmj",
    "entendi",
    "recebi",
    "nada",
    "de",
}
_MAX_ACK_TOKENS = 6


@dataclass(frozen=True, slots=True)
class RuleResult:
    sector: str | None
    kind: str | None
    urgency: str
    noise: bool
    attach_reply: bool
    sector_candidates: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return (
            self.noise or self.attach_reply or (self.sector is not None and self.kind is not None)
        )


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", stripped.lower()).strip()


def _tokens(normalized: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalized)


def _sector_scores(text: str, normalized: str) -> dict[str, int]:
    scores: dict[str, int] = {}
    for sector, patterns in _SECTOR_KEYWORDS.items():
        total = sum(weight * len(re.findall(p, normalized)) for p, weight in patterns)
        if total:
            scores[sector] = total
    if _DAS_UPPERCASE.search(text):
        scores["fiscal"] = scores.get("fiscal", 0) + 1
    return scores


def _pick_sector(
    scores: dict[str, int], normalized: str, context: Context
) -> tuple[str | None, tuple[str, ...]]:
    if context.contact_type == "colaborador" and _HR_INTERNAL.search(normalized):
        return "rh-interno", ()
    if not scores:
        return None, ()
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_score = ranked[0][1]
    if len(ranked) == 1 or top_score - ranked[1][1] >= 1:
        return ranked[0][0], ()
    return None, tuple(sector for sector, score in ranked if score == top_score)


def _pick_kind(normalized: str, context: Context) -> str | None:
    for kind, pattern in _KIND_PATTERNS:
        if pattern.search(normalized):
            return kind
    if context.has_media and re.search(r"\b(segue|anexo|mandando|enviei|encaminho)\b", normalized):
        return "documento"
    return None


def _urgency(normalized: str, kind: str | None) -> str:
    if _CRITICAL.search(normalized):
        urgency = "critica"
    elif _HIGH.search(normalized):
        urgency = "alta"
    else:
        urgency = "normal"
    # reclamacao nunca e rotina: no minimo alta
    return max_urgency(urgency, "alta") if kind == "reclamacao" else urgency


def classify_by_rules(text: str, context: Context) -> RuleResult:
    normalized = normalize(text)
    tokens = _tokens(normalized)
    token_set = set(tokens)

    if normalized and not tokens:
        # so pontuacao ou simbolos (figurinha, emoji): nao ha demanda
        return RuleResult(None, None, "normal", True, False, ())

    is_greeting_or_ack = bool(tokens) and token_set <= _GREETING_TOKENS | _ACK_TOKENS
    only_greeting = bool(tokens) and token_set <= _GREETING_TOKENS
    if is_greeting_or_ack and len(tokens) <= _MAX_ACK_TOKENS:
        if only_greeting or not context.has_open_demand:
            return RuleResult(None, None, "normal", True, False, ())
        return RuleResult(None, None, "normal", False, True, ())

    scores = _sector_scores(text, normalized)
    sector, candidates = _pick_sector(scores, normalized, context)
    kind = _pick_kind(normalized, context)
    return RuleResult(sector, kind, _urgency(normalized, kind), False, False, candidates)
