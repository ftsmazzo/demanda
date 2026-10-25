"""Orquestra regras, IA e fallback. Nunca perde a mensagem: no pior caso vai para a triagem."""

import logging

from app.classification.domain import (
    Classification,
    Context,
    Decision,
    LLMOutput,
    max_urgency,
)
from app.classification.llm import ClassifierUnavailable, LLMClassifier
from app.classification.rules import RuleResult, classify_by_rules

logger = logging.getLogger(__name__)

RULE_CONFIDENCE = 0.9
DEFAULT_THRESHOLD = 0.6
_MAX_LOGGED_ERROR = 200


def classify_message(
    text: str,
    context: Context,
    *,
    llm: LLMClassifier | None = None,
    threshold: float = DEFAULT_THRESHOLD,
) -> Decision:
    rules = classify_by_rules(text, context)
    default_sector = context.channel_default_sector or "triagem"

    if rules.attach_reply:
        return Decision(
            "attach_reply",
            Classification(
                default_sector,
                "indefinido",
                "normal",
                None,
                RULE_CONFIDENCE,
                "rule",
                reason="short_reply",
            ),
        )
    if rules.noise:
        return Decision(
            "noise",
            Classification(default_sector, "ruido", "normal", None, RULE_CONFIDENCE, "rule"),
        )
    if rules.complete:
        return Decision(
            "classified",
            Classification(rules.sector, rules.kind, rules.urgency, None, RULE_CONFIDENCE, "rule"),
        )
    if not text.strip():
        return _fallback(rules, context, "no_text")
    if llm is None:
        return _fallback(rules, context, "no_llm")

    hints = {
        "sector_candidates": list(rules.sector_candidates),
        "sector": rules.sector,
        "kind": rules.kind,
        "urgency": rules.urgency,
    }
    try:
        output = llm.classify(text, context, hints)
    except ClassifierUnavailable as exc:
        logger.warning("IA indisponivel; mensagem segue para a triagem: %s", exc)
        return _fallback(rules, context, "llm_unavailable")
    except ValueError as exc:
        logger.warning(
            "resposta invalida da IA; mensagem segue para a triagem: %s",
            str(exc)[:_MAX_LOGGED_ERROR],
        )
        return _fallback(rules, context, "llm_invalid")
    except Exception:
        logger.exception("erro inesperado na IA; mensagem segue para a triagem")
        return _fallback(rules, context, "llm_error")

    return _from_llm(output, rules, context, threshold)


def _from_llm(output: LLMOutput, rules: RuleResult, context: Context, threshold: float) -> Decision:
    # a confianca vale para tudo, inclusive para "isto e ruido": duvida vai para revisao
    if output.confidence < threshold:
        return _fallback(rules, context, "low_confidence")
    if output.is_noise:
        return Decision(
            "noise",
            Classification(
                context.channel_default_sector or "triagem",
                "ruido",
                "normal",
                None,
                output.confidence,
                "llm",
            ),
        )
    return Decision(
        "classified",
        Classification(
            output.sector,
            output.kind,
            max_urgency(rules.urgency, output.urgency),
            output.client_hint,
            output.confidence,
            "llm",
        ),
    )


def _fallback(rules: RuleResult, context: Context, reason: str) -> Decision:
    sector = rules.sector or context.channel_default_sector or "triagem"
    return Decision(
        "classified",
        Classification(
            sector,
            rules.kind or "indefinido",
            rules.urgency,
            None,
            0.0,
            "fallback",
            needs_review=True,
            reason=reason,
        ),
    )
