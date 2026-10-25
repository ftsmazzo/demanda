from datetime import UTC, datetime, timedelta

import pytest

from app.classification.domain import ACTIONS, SECTORS, SOURCES, STORED_KINDS, URGENCIES
from app.classification.llm import ClassifierUnavailable
from app.classification.rules import RULES_VERSION
from app.classification.store import classify_pending
from tests.conftest import ChannelFixture
from tests.test_classification_service import FakeLLM, llm_output

BASE = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def add_message(
    conn,
    channel: ChannelFixture,
    message_id,
    text,
    *,
    direction="in",
    phone="5511999990101",
    minutes=0,
    media=None,
):
    contact_id = conn.execute(
        "INSERT INTO contacts (tenant_id, phone) VALUES (%s, %s) "
        "ON CONFLICT (tenant_id, phone) DO UPDATE SET phone = EXCLUDED.phone RETURNING id",
        (channel.tenant_id, phone),
    ).fetchone()[0]
    row = conn.execute(
        "INSERT INTO messages (tenant_id, channel_id, provider_message_id, direction, remote_jid, "
        "contact_phone, message_type, text, media, provider_timestamp, raw, contact_id) "
        "VALUES (%s, %s, %s, %s, %s, %s, 'conversation', %s, %s, %s, '{}'::jsonb, %s) RETURNING id",
        (
            channel.tenant_id,
            channel.channel_id,
            message_id,
            direction,
            f"{phone}@s.whatsapp.net",
            phone,
            text,
            None if media is None else '{"mimetype": "image/jpeg"}',
            BASE + timedelta(minutes=minutes),
            contact_id,
        ),
    )
    return row.fetchone()[0]


def stored(admin_conn, message_id):
    return admin_conn.execute(
        "SELECT action, sector, kind, urgency, source, needs_review, reason, model, rules_version "
        "FROM message_classifications WHERE message_id = %s",
        (message_id,),
    ).fetchall()


def test_inbound_messages_are_classified_and_stored(database, admin_conn, channel):
    fiscal = add_message(admin_conn, channel, "S1", "Quando vence o DAS esse mes?")
    noise = add_message(admin_conn, channel, "S2", "Bom dia!", minutes=1)

    counts = classify_pending(database, channel.tenant_id)

    assert counts["classified"] == 1
    assert counts["noise"] == 1
    assert stored(admin_conn, fiscal) == [
        ("classified", "fiscal", "duvida", "normal", "rule", False, None, None, RULES_VERSION)
    ]
    assert stored(admin_conn, noise)[0][0] == "noise"


def test_outbound_messages_are_not_classified(database, admin_conn, channel):
    sent = add_message(admin_conn, channel, "S3", "Segue a guia", direction="out")

    classify_pending(database, channel.tenant_id)

    assert stored(admin_conn, sent) == []


def test_running_twice_does_not_duplicate(database, admin_conn, channel):
    message = add_message(admin_conn, channel, "S4", "Quando vence o DAS esse mes?")

    classify_pending(database, channel.tenant_id)
    second = classify_pending(database, channel.tenant_id)

    assert sum(second.values()) == 0
    assert len(stored(admin_conn, message)) == 1


def test_limit_processes_the_oldest_first(database, admin_conn, channel):
    first = add_message(admin_conn, channel, "S5", "Quando vence o DAS esse mes?", minutes=0)
    later = add_message(admin_conn, channel, "S6", "Quando vence o DAS esse mes?", minutes=5)

    classify_pending(database, channel.tenant_id, limit=1)

    assert len(stored(admin_conn, first)) == 1
    assert stored(admin_conn, later) == []


def test_media_without_text_is_sent_to_review_not_lost(database, admin_conn, channel):
    message = add_message(admin_conn, channel, "S7", None, media=True)

    classify_pending(database, channel.tenant_id)

    row = stored(admin_conn, message)[0]
    assert row[1] == "triagem"
    assert row[5] is True
    assert row[6] == "no_text"


def test_llm_receives_the_recent_conversation_of_the_same_contact(database, admin_conn, channel):
    add_message(admin_conn, channel, "S8", "Oi, tudo bem?", minutes=0)
    add_message(admin_conn, channel, "S9", "Pode me ajudar com uma coisa aqui?", minutes=1)
    add_message(
        admin_conn, channel, "S10", "Mensagem de outra pessoa", phone="5511999990999", minutes=2
    )
    llm = FakeLLM(llm_output(sector="dp", kind="duvida"))

    classify_pending(database, channel.tenant_id, llm=llm)

    context = llm.calls[0][1]
    assert context.recent == ("Oi, tudo bem?",)


def test_llm_answer_is_stored_with_model_name(database, admin_conn, channel):
    message = add_message(admin_conn, channel, "S11", "Pode me ajudar com uma coisa aqui?")
    llm = FakeLLM(llm_output(sector="dp", kind="duvida", client_hint="Padaria"))
    llm.model = "modelo-de-teste"

    classify_pending(database, channel.tenant_id, llm=llm)

    row = stored(admin_conn, message)[0]
    assert (row[1], row[2], row[4], row[7]) == ("dp", "duvida", "llm", "modelo-de-teste")
    hint = admin_conn.execute(
        "SELECT client_hint FROM message_classifications WHERE message_id = %s", (message,)
    ).fetchone()[0]
    assert hint == "Padaria"


def test_temporary_llm_outage_leaves_the_message_pending_for_the_next_run(
    database, admin_conn, channel
):
    message = add_message(admin_conn, channel, "S12", "Pode me ajudar com uma coisa aqui?")

    first = classify_pending(
        database, channel.tenant_id, llm=FakeLLM(error=ClassifierUnavailable("x"))
    )
    assert first["deferred"] == 1
    assert stored(admin_conn, message) == []

    second = classify_pending(
        database, channel.tenant_id, llm=FakeLLM(llm_output(sector="dp", kind="duvida"))
    )
    assert second["classified"] == 1
    assert stored(admin_conn, message)[0][1] == "dp"


def test_classifications_are_isolated_by_tenant(
    database, admin_conn, app_conn, channel, other_channel
):
    add_message(admin_conn, channel, "S13", "Quando vence o DAS esse mes?")
    add_message(admin_conn, other_channel, "S14", "Quando vence o DAS esse mes?")
    classify_pending(database, channel.tenant_id)
    classify_pending(database, other_channel.tenant_id)

    app_conn.execute("SELECT set_config('app.tenant_id', %s, false)", (str(channel.tenant_id),))

    assert app_conn.execute("SELECT count(*) FROM message_classifications").fetchone()[0] == 1


def test_one_tenant_cannot_classify_another_tenants_messages(
    database, admin_conn, channel, other_channel
):
    foreign = add_message(admin_conn, other_channel, "S15", "Quando vence o DAS esse mes?")

    classify_pending(database, channel.tenant_id)

    assert stored(admin_conn, foreign) == []


@pytest.mark.parametrize(
    ("column", "values"),
    [
        ("action", ACTIONS),
        ("sector", SECTORS),
        ("kind", STORED_KINDS),
        ("urgency", URGENCIES),
        ("source", SOURCES),
    ],
)
def test_every_domain_value_is_accepted_by_the_database_constraints(
    admin_conn, channel, column, values
):
    message = add_message(admin_conn, channel, f"V-{column}", "texto")
    base = {
        "action": "classified",
        "sector": "triagem",
        "kind": "tarefa",
        "urgency": "normal",
        "source": "rule",
    }
    for value in values:
        row = {**base, column: value}
        admin_conn.execute(
            "INSERT INTO message_classifications (tenant_id, message_id, action, sector, kind, "
            "urgency, confidence, source, rules_version) "
            "VALUES (%s, %s, %s, %s, %s, %s, 0.5, %s, %s)",
            (
                channel.tenant_id,
                message,
                row["action"],
                row["sector"],
                row["kind"],
                row["urgency"],
                row["source"],
                f"t-{column}-{value}",
            ),
        )


def test_unexpected_error_in_one_message_does_not_block_the_batch(database, admin_conn, channel):
    first = add_message(admin_conn, channel, "E1", "Pode me ajudar com uma coisa aqui?", minutes=0)
    second = add_message(admin_conn, channel, "E2", "Quando vence o DAS esse mes?", minutes=1)

    counts = classify_pending(database, channel.tenant_id, llm=FakeLLM(error=RuntimeError("boom")))

    assert counts["deferred"] == 1
    assert stored(admin_conn, first) == []
    assert stored(admin_conn, second)[0][1] == "fiscal"


def test_other_tenants_rows_are_filtered_in_the_recent_history_query(
    database, admin_conn, channel, other_channel
):
    add_message(admin_conn, other_channel, "H1", "Historico de outro tenant", phone="5511999990101")
    add_message(admin_conn, channel, "H2", "Pode me ajudar com uma coisa aqui?", minutes=5)
    llm = FakeLLM(llm_output(sector="dp", kind="duvida"))

    classify_pending(database, channel.tenant_id, llm=llm)

    assert llm.calls[0][1].recent == ()


def all_rows(admin_conn, message_id):
    return admin_conn.execute(
        "SELECT source, reason, sector FROM message_classifications "
        "WHERE message_id = %s ORDER BY created_at, id",
        (message_id,),
    ).fetchall()


def test_rules_only_fallback_is_reclassified_once_an_llm_is_available(
    database, admin_conn, channel
):
    message = add_message(admin_conn, channel, "N1", "Pode me ajudar com uma coisa aqui?")

    classify_pending(database, channel.tenant_id)
    assert all_rows(admin_conn, message) == [("fallback", "no_llm", "triagem")]

    counts = classify_pending(
        database, channel.tenant_id, llm=FakeLLM(llm_output(sector="dp", kind="duvida"))
    )

    assert counts["classified"] == 1
    assert all_rows(admin_conn, message) == [
        ("fallback", "no_llm", "triagem"),
        ("llm", None, "dp"),
    ]


def test_rules_only_runs_do_not_pile_up_no_llm_rows(database, admin_conn, channel):
    message = add_message(admin_conn, channel, "N2", "Pode me ajudar com uma coisa aqui?")

    classify_pending(database, channel.tenant_id)
    second = classify_pending(database, channel.tenant_id)

    assert sum(second.values()) == 0
    assert len(all_rows(admin_conn, message)) == 1


def test_definitive_llm_results_are_not_redone(database, admin_conn, channel):
    message = add_message(admin_conn, channel, "N3", "Pode me ajudar com uma coisa aqui?")
    llm = FakeLLM(llm_output(sector="dp", kind="duvida"))

    classify_pending(database, channel.tenant_id, llm=llm)
    second = classify_pending(database, channel.tenant_id, llm=llm)

    assert sum(second.values()) == 0
    assert len(all_rows(admin_conn, message)) == 1


def test_known_employee_contact_triggers_the_internal_hr_rule(database, admin_conn, channel):
    message = add_message(
        admin_conn, channel, "X1", "Preciso de folga dia 30, posso?", phone="5511999990104"
    )
    admin_conn.execute(
        "UPDATE contacts SET kind = 'colaborador' WHERE tenant_id = %s AND phone = %s",
        (channel.tenant_id, "5511999990104"),
    )

    classify_pending(database, channel.tenant_id)

    assert stored(admin_conn, message)[0][1] == "rh-interno"


def _contact_of(admin_conn, message_id):
    return admin_conn.execute(
        "SELECT contact_id FROM messages WHERE id = %s", (message_id,)
    ).fetchone()[0]


def test_short_acknowledgement_with_an_open_demand_is_attached_not_noise(
    database, admin_conn, channel
):
    from tests.test_core_schema import make_demand

    first = add_message(admin_conn, channel, "X2", "Quando vence o DAS esse mes?", minutes=0)
    make_demand(admin_conn, channel.tenant_id, contact_id=_contact_of(admin_conn, first))
    ack = add_message(admin_conn, channel, "X3", "ok", minutes=5)

    classify_pending(database, channel.tenant_id)

    assert stored(admin_conn, ack)[0][0] == "attach_reply"


def test_acknowledgement_after_the_demand_was_closed_is_noise(database, admin_conn, channel):
    from tests.test_core_schema import make_demand

    first = add_message(admin_conn, channel, "X4", "Quando vence o DAS esse mes?", minutes=0)
    make_demand(
        admin_conn, channel.tenant_id, contact_id=_contact_of(admin_conn, first), status="concluido"
    )
    ack = add_message(admin_conn, channel, "X5", "ok", minutes=5)

    classify_pending(database, channel.tenant_id)

    assert stored(admin_conn, ack)[0][0] == "noise"
