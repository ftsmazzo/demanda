import pytest

from app.classification.domain import Context
from app.classification.evaluation import GoldenCase, evaluate, load_golden

MIN_RULE_PRECISION = 0.9
MIN_RULE_COVERAGE = 0.5


def case(case_id, text, sector, kind, urgency="normal", action="classified", **ctx):
    expected = {"action": action, "sector": sector, "kind": kind, "urgency": urgency}
    return GoldenCase(case_id, text, Context(**ctx), expected)


def test_golden_set_is_loaded_with_context_and_labels():
    cases = load_golden()

    assert len(cases) >= 50
    assert len({c.id for c in cases}) == len(cases)
    first = cases[0]
    assert first.expected["sector"] == "fiscal"
    assert first.context.has_media is True
    assert {c.expected["action"] for c in cases} == {"classified", "noise", "attach_reply"}


def test_metrics_on_a_tiny_set():
    cases = [
        case("a", "Quando vence o DAS esse mes?", "fiscal", "duvida"),
        case("b", "Quando vence o DAS esse mes?", "dp", "duvida"),
        case("c", "Pode me ajudar com uma coisa aqui?", "fiscal", "duvida"),
        case("d", "Bom dia!", "triagem", "ruido", action="noise"),
    ]

    report = evaluate(cases, llm=None)

    assert report.total == 4
    assert report.source_counts == {"rule": 3, "fallback": 1}
    assert report.rule_coverage == pytest.approx(0.75)
    assert report.rule_precision == pytest.approx(2 / 3)
    assert report.review_rate == pytest.approx(0.25)
    assert report.accuracy["action"] == pytest.approx(1.0)
    assert report.accuracy["sector"] == pytest.approx(1 / 3)
    assert [error.case_id for error in report.errors] == ["b", "c"]


def test_rules_alone_meet_the_quality_floor_on_the_golden_set():
    report = evaluate(load_golden(), llm=None)

    assert report.rule_precision >= MIN_RULE_PRECISION, report.render()
    assert report.rule_coverage >= MIN_RULE_COVERAGE, report.render()


def test_evaluation_with_llm_and_no_key_explains_and_fails(monkeypatch, capsys):
    from app.classification.evaluation import main

    for name in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "CLASSIFIER_PROVIDER"):
        monkeypatch.delenv(name, raising=False)

    assert main(["--llm"]) == 2
    assert "OPENROUTER_API_KEY" in capsys.readouterr().out
