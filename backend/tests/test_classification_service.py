import pytest

from app.classification.domain import Context, LLMOutput
from app.classification.llm import ClassifierUnavailable, parse_llm_output
from app.classification.service import classify_message


class FakeLLM:
    def __init__(self, output=None, error=None):
        self.output = output
        self.error = error
        self.calls = []

    def classify(self, text, context, hints):
        self.calls.append((text, context, hints))
        if self.error:
            raise self.error
        return self.output


def llm_output(**overrides):
    base = {
        "sector": "contabil",
        "kind": "tarefa",
        "urgency": "normal",
        "client_hint": None,
        "confidence": 0.9,
        "is_noise": False,
    }
    base.update(overrides)
    return LLMOutput(**base)


AMBIGUOUS = "Pode me ajudar com uma coisa aqui?"


def test_complete_rule_match_skips_the_llm():
    llm = FakeLLM(llm_output())

    decision = classify_message("Quando vence o DAS esse mes?", Context(), llm=llm)

    assert llm.calls == []
    assert decision.action == "classified"
    assert decision.classification.source == "rule"
    assert decision.classification.sector == "fiscal"
    assert not decision.classification.needs_review


def test_unresolved_message_goes_to_the_llm_and_uses_its_answer():
    llm = FakeLLM(llm_output(sector="dp", kind="duvida", client_hint="Padaria Pao Quente"))

    decision = classify_message(AMBIGUOUS, Context(), llm=llm)

    assert len(llm.calls) == 1
    assert decision.classification.source == "llm"
    assert decision.classification.sector == "dp"
    assert decision.classification.kind == "duvida"
    assert decision.classification.client_hint == "Padaria Pao Quente"


def test_rule_hints_are_passed_to_the_llm():
    llm = FakeLLM(llm_output())

    classify_message("Preciso do balancete e da guia", Context(), llm=llm)

    assert llm.calls[0][2]["sector_candidates"]


def test_low_confidence_falls_back_to_triage_and_asks_for_review():
    llm = FakeLLM(llm_output(confidence=0.3))

    decision = classify_message(AMBIGUOUS, Context(), llm=llm)

    assert decision.classification.source == "fallback"
    assert decision.classification.sector == "triagem"
    assert decision.classification.needs_review
    assert decision.classification.reason == "low_confidence"


def test_fallback_prefers_the_channel_default_sector():
    decision = classify_message(
        AMBIGUOUS, Context(channel_default_sector="dp"), llm=FakeLLM(llm_output(confidence=0.1))
    )

    assert decision.classification.sector == "dp"


def test_llm_outage_never_loses_the_message():
    llm = FakeLLM(error=ClassifierUnavailable("down"))

    decision = classify_message(AMBIGUOUS, Context(), llm=llm)

    assert decision.action == "classified"
    assert decision.classification.sector == "triagem"
    assert decision.classification.reason == "llm_unavailable"
    assert decision.classification.needs_review


def test_invalid_llm_answer_is_handled_as_fallback():
    llm = FakeLLM(error=ValueError("bad enum"))

    decision = classify_message(AMBIGUOUS, Context(), llm=llm)

    assert decision.classification.reason == "llm_invalid"
    assert decision.classification.needs_review


def test_without_an_llm_unresolved_messages_go_to_triage():
    decision = classify_message(AMBIGUOUS, Context(), llm=None)

    assert decision.classification.reason == "no_llm"
    assert decision.classification.sector == "triagem"


def test_urgency_is_the_highest_of_rules_and_llm():
    llm = FakeLLM(llm_output(urgency="normal"))

    decision = classify_message("Urgente, me ajuda com uma coisa aqui?", Context(), llm=llm)

    assert decision.classification.urgency == "alta"


def test_llm_can_flag_noise():
    llm = FakeLLM(llm_output(is_noise=True))

    decision = classify_message(AMBIGUOUS, Context(), llm=llm)

    assert decision.action == "noise"


def test_acknowledgement_with_open_demand_attaches_without_calling_the_llm():
    llm = FakeLLM(llm_output())

    decision = classify_message("ok", Context(has_open_demand=True), llm=llm)

    assert decision.action == "attach_reply"
    assert llm.calls == []


def test_greeting_is_noise_without_calling_the_llm():
    llm = FakeLLM(llm_output())

    decision = classify_message("Bom dia!", Context(), llm=llm)

    assert decision.action == "noise"
    assert llm.calls == []


VALID = {
    "sector": "fiscal",
    "kind": "duvida",
    "urgency": "alta",
    "client_hint": "Oficina do Ze",
    "confidence": 0.82,
    "is_noise": False,
}


def test_parse_llm_output_accepts_a_valid_answer():
    out = parse_llm_output(VALID)

    assert out.sector == "fiscal"
    assert out.confidence == pytest.approx(0.82)


@pytest.mark.parametrize(
    "patch",
    [
        {"sector": "marketing"},
        {"kind": "outro"},
        {"urgency": "maxima"},
        {"confidence": 1.5},
        {"confidence": -0.1},
        {"confidence": "alta"},
        {"is_noise": "sim"},
    ],
)
def test_parse_llm_output_rejects_invalid_values(patch):
    with pytest.raises(ValueError):
        parse_llm_output({**VALID, **patch})


def test_parse_llm_output_rejects_missing_fields():
    data = dict(VALID)
    del data["sector"]

    with pytest.raises(ValueError):
        parse_llm_output(data)


def test_parse_llm_output_truncates_long_client_hint_and_accepts_null():
    assert len(parse_llm_output({**VALID, "client_hint": "x" * 500}).client_hint) <= 100
    assert parse_llm_output({**VALID, "client_hint": None}).client_hint is None


def test_noise_flag_from_a_low_confidence_llm_still_goes_to_review():
    llm = FakeLLM(llm_output(is_noise=True, confidence=0.3))

    decision = classify_message(AMBIGUOUS, Context(), llm=llm)

    assert decision.action == "classified"
    assert decision.classification.needs_review
    assert decision.classification.reason == "low_confidence"


def test_unexpected_llm_exception_is_also_a_fallback():
    llm = FakeLLM(error=RuntimeError("inesperado"))

    decision = classify_message(AMBIGUOUS, Context(), llm=llm)

    assert decision.classification.reason == "llm_error"
    assert decision.classification.needs_review
