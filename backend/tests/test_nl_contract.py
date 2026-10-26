import pytest

from app.agent.nl.contract import Intent, parse_intent


def good(**overrides):
    data = {
        "intent": "create_task",
        "confidence": 0.9,
        "title": "Conferir a folha do Mercado Bom Preco",
        "sector": "dp",
        "assignee_name": "Bruno",
        "contact_name": "Mercado Bom Preco",
        "urgency": "alta",
        "due_phrase": "sexta",
        "case_text": None,
        "status": None,
        "status_filter": None,
        "range": None,
        "priority_only": False,
        "priority_value": None,
    }
    data.update(overrides)
    return data


def test_a_task_request_is_parsed():
    intent = parse_intent(good())

    assert isinstance(intent, Intent)
    assert intent.intent == "create_task"
    assert intent.title == "Conferir a folha do Mercado Bom Preco"
    assert (intent.sector, intent.assignee_name) == ("dp", "Bruno")
    assert intent.due_phrase == "sexta" and intent.urgency == "alta"


def test_queries_need_no_extra_fields_and_agenda_defaults_to_today():
    assert parse_intent(good(intent="query_demands", title=None)).intent == "query_demands"
    assert parse_intent(good(intent="query_agenda", range=None)).range == "today"
    assert parse_intent(good(intent="query_agenda", range="week")).range == "week"
    assert parse_intent(good(intent="summary")).intent == "summary"


def test_required_fields_per_intent():
    with pytest.raises(ValueError):
        parse_intent(good(intent="create_task", title=None))
    with pytest.raises(ValueError):
        parse_intent(good(intent="assign", case_text=None, assignee_name="Bruno"))
    with pytest.raises(ValueError):
        parse_intent(good(intent="assign", case_text="folha", assignee_name=None))
    with pytest.raises(ValueError):
        parse_intent(good(intent="set_status", case_text="folha", status=None))
    with pytest.raises(ValueError):
        parse_intent(good(intent="mark_priority", contact_name=None, priority_value=True))
    with pytest.raises(ValueError):
        parse_intent(good(intent="mark_priority", contact_name="Padaria", priority_value=None))


def test_a_reschedule_needs_the_appointment_and_the_new_time():
    ok = parse_intent(good(intent="reschedule", case_text="reuniao IE", due_phrase="quinta 15h"))
    assert (ok.case_text, ok.due_phrase) == ("reuniao IE", "quinta 15h")
    with pytest.raises(ValueError):
        parse_intent(good(intent="reschedule", case_text="reuniao IE", due_phrase=None))
    with pytest.raises(ValueError):
        parse_intent(good(intent="reschedule", case_text=None, due_phrase="quinta 15h"))


def test_valid_assign_status_and_priority_requests():
    assign = parse_intent(good(intent="assign", case_text="folha de outubro", assignee_name="Ana"))
    status = parse_intent(good(intent="set_status", case_text="folha", status="concluido"))
    star = parse_intent(good(intent="mark_priority", contact_name="Padaria", priority_value=False))

    assert (assign.case_text, assign.assignee_name) == ("folha de outubro", "Ana")
    assert status.status == "concluido"
    assert star.priority_value is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"intent": "delete_everything"},
        {"sector": "marketing"},
        {"urgency": "urgentissima"},
        {"status": "feito"},
        {"status_filter": "tudo"},
        {"range": "mes"},
        {"confidence": 2},
        {"confidence": True},
        {"title": 7},
        {"priority_only": "sim"},
        {"priority_value": "sim"},
    ],
)
def test_anything_off_contract_is_refused(overrides):
    with pytest.raises(ValueError):
        parse_intent(good(**overrides))


def test_texts_are_trimmed_and_cut_and_unknown_needs_nothing():
    cut = parse_intent(good(title="  " + "t" * 500 + "  ", assignee_name="a" * 300))
    unknown = parse_intent({"intent": "unknown", "confidence": 0.1})

    assert len(cut.title) <= 120 and len(cut.assignee_name) <= 80
    assert unknown.intent == "unknown"
    for bad in (None, [], "texto"):
        with pytest.raises(ValueError):
            parse_intent(bad)


def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def test_the_provider_schema_uses_plain_enums_and_no_nullable_booleans():
    from app.agent.nl.contract import OUTPUT_SCHEMA

    for node in _walk(OUTPUT_SCHEMA):
        if "enum" in node:
            assert None not in node["enum"], node
            assert node.get("type") == "string", node
        assert node.get("type") != ["boolean", "null"], node


def test_the_none_marker_means_no_value():
    intent = parse_intent(
        good(
            intent="query_demands",
            sector="none",
            urgency="none",
            status="none",
            status_filter="none",
            range="none",
            priority_value="none",
        )
    )

    assert (intent.sector, intent.urgency, intent.status) == (None, None, None)
    assert (intent.status_filter, intent.range, intent.priority_value) == (None, None, None)


def test_yes_and_no_work_as_the_priority_value():
    star = parse_intent(good(intent="mark_priority", contact_name="Padaria", priority_value="yes"))
    off = parse_intent(good(intent="mark_priority", contact_name="Padaria", priority_value="no"))

    assert star.priority_value is True and off.priority_value is False
