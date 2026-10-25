from app.classification.factory import build_classifier
from app.classification.llm import AnthropicClassifier
from app.classification.openrouter import OpenRouterClassifier


def test_openrouter_key_selects_openrouter():
    classifier, description = build_classifier({"OPENROUTER_API_KEY": "k"})

    assert isinstance(classifier, OpenRouterClassifier)
    assert "OpenRouter" in description


def test_anthropic_key_selects_anthropic_when_no_openrouter_key():
    classifier, description = build_classifier({"ANTHROPIC_API_KEY": "k"})

    assert isinstance(classifier, AnthropicClassifier)
    assert "Anthropic" in description


def test_openrouter_wins_when_both_keys_exist():
    classifier, _ = build_classifier({"OPENROUTER_API_KEY": "a", "ANTHROPIC_API_KEY": "b"})

    assert isinstance(classifier, OpenRouterClassifier)


def test_explicit_provider_overrides_the_automatic_choice():
    env = {"OPENROUTER_API_KEY": "a", "ANTHROPIC_API_KEY": "b", "CLASSIFIER_PROVIDER": "anthropic"}

    classifier, _ = build_classifier(env)

    assert isinstance(classifier, AnthropicClassifier)


def test_none_provider_disables_the_llm_even_with_keys():
    classifier, _ = build_classifier({"OPENROUTER_API_KEY": "a", "CLASSIFIER_PROVIDER": "none"})

    assert classifier is None


def test_without_any_key_there_is_no_llm_and_the_message_names_both_variables():
    classifier, description = build_classifier({})

    assert classifier is None
    assert "OPENROUTER_API_KEY" in description
    assert "ANTHROPIC_API_KEY" in description


def test_explicit_provider_without_its_key_has_no_llm():
    classifier, description = build_classifier({"CLASSIFIER_PROVIDER": "openrouter"})

    assert classifier is None
    assert "OPENROUTER_API_KEY" in description
