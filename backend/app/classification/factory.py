"""Escolhe o classificador de IA pelas variaveis de ambiente (ou nenhum)."""

from collections.abc import Mapping

from app.classification.llm import AnthropicClassifier, LLMClassifier
from app.classification.openrouter import OpenRouterClassifier

_NO_KEY = "sem IA (defina OPENROUTER_API_KEY ou ANTHROPIC_API_KEY): classificando so com regras"


def build_classifier(env: Mapping[str, str]) -> tuple[LLMClassifier | None, str]:
    """Devolve (classificador ou None, descricao curta para mostrar ao usuario).

    CLASSIFIER_PROVIDER = openrouter | anthropic | none forca a escolha; sem ele vale a ordem
    OPENROUTER_API_KEY, depois ANTHROPIC_API_KEY.
    """
    provider = (env.get("CLASSIFIER_PROVIDER") or "").strip().lower()
    openrouter_key = env.get("OPENROUTER_API_KEY")
    anthropic_key = env.get("ANTHROPIC_API_KEY")

    if provider == "none":
        return None, "IA desligada por CLASSIFIER_PROVIDER=none: classificando so com regras"
    if provider == "openrouter" or (not provider and openrouter_key):
        if not openrouter_key:
            return None, "CLASSIFIER_PROVIDER=openrouter sem OPENROUTER_API_KEY: so regras"
        classifier = OpenRouterClassifier(api_key=openrouter_key)
        return classifier, f"IA via OpenRouter, modelo {classifier.model}"
    if provider == "anthropic" or (not provider and anthropic_key):
        if not anthropic_key:
            return None, "CLASSIFIER_PROVIDER=anthropic sem ANTHROPIC_API_KEY: so regras"
        classifier = AnthropicClassifier()
        return classifier, f"IA via Anthropic, modelo {classifier.model}"
    return None, _NO_KEY
