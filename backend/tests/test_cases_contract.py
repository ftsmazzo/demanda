import pytest

from app.cases.contract import CaseDecision, parse_case_output


def good(**overrides):
    data = {
        "action": "new",
        "case_ref": None,
        "confidence": 0.9,
        "kind": "nota",
        "sector": "rh-interno",
        "urgency": "normal",
        "title": "Pedido de férias de Ana",
        "summary": "A funcionária Ana pediu férias para dezembro.",
        "next_step": "Lançar as férias no sistema de RH.",
        "when_phrase": None,
        "appointment_ref": None,
        "reason": "assunto novo do escritório",
    }
    data.update(overrides)
    return data


def test_a_valid_new_case_is_parsed_and_trimmed():
    decision = parse_case_output(good(title="  Pedido de férias  "), open_cases=0, appointments=0)

    assert isinstance(decision, CaseDecision)
    assert (decision.action, decision.kind, decision.sector) == ("new", "nota", "rh-interno")
    assert decision.title == "Pedido de férias"
    assert decision.confidence == 0.9


def test_attach_needs_a_case_that_exists_in_the_list_we_sent():
    ok = parse_case_output(good(action="attach", case_ref=2), open_cases=2, appointments=0)
    assert ok.case_ref == 2

    for bad_ref in (0, 3, None, "1", True):
        with pytest.raises(ValueError):
            parse_case_output(good(action="attach", case_ref=bad_ref), open_cases=2, appointments=0)


def test_a_new_case_must_not_point_at_an_existing_one():
    with pytest.raises(ValueError):
        parse_case_output(good(action="new", case_ref=1), open_cases=2, appointments=0)


def test_ignore_needs_no_case_data():
    decision = parse_case_output(
        {"action": "ignore", "confidence": 0.95, "reason": "agradecimento"},
        open_cases=0,
        appointments=0,
    )

    assert decision.action == "ignore" and decision.title == ""


@pytest.mark.parametrize(
    "overrides",
    [
        {"action": "delete"},
        {"kind": "ferias"},
        {"sector": "marketing"},
        {"urgency": "urgentissima"},
        {"confidence": 1.5},
        {"confidence": -0.1},
        {"confidence": True},
        {"confidence": "alta"},
        {"title": ""},
        {"title": "   "},
        {"title": 12},
        {"summary": None},
        {"next_step": 5},
        {"when_phrase": 7},
        {"appointment_ref": 1},
    ],
)
def test_anything_off_contract_is_refused(overrides):
    with pytest.raises(ValueError):
        parse_case_output(good(**overrides), open_cases=1, appointments=0)


def test_an_appointment_ref_must_be_one_we_sent():
    ok = parse_case_output(
        good(when_phrase="quinta às 10", appointment_ref=1), open_cases=1, appointments=1
    )
    assert ok.appointment_ref == 1 and ok.when_phrase == "quinta às 10"

    with pytest.raises(ValueError):
        parse_case_output(
            good(when_phrase="quinta", appointment_ref=2), open_cases=1, appointments=1
        )


def test_long_texts_are_cut_not_trusted():
    decision = parse_case_output(
        good(title="t" * 500, summary="s" * 5000, next_step="n" * 900, when_phrase="w" * 400),
        open_cases=0,
        appointments=0,
    )

    assert len(decision.title) <= 120
    assert len(decision.summary) <= 400
    assert len(decision.next_step) <= 200
    assert len(decision.when_phrase) <= 80


def test_not_an_object_is_refused():
    for bad in (None, [], "texto", 3):
        with pytest.raises(ValueError):
            parse_case_output(bad, open_cases=0, appointments=0)
