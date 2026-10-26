from app.cases.service import materialize_cases

from app.classification.llm import ClassifierUnavailable
from tests.cases_helpers import FakeCaseLLM, decision, demands_of, events_of, phone, say


def run(database, tenant_id, llm, **kwargs):
    return materialize_cases(database, tenant_id, llm, **kwargs)


def linked(conn, demand_id):
    return conn.execute(
        "SELECT count(*) FROM demand_messages WHERE demand_id = %s", (demand_id,)
    ).fetchone()[0]


def test_a_new_case_gets_the_ai_title_summary_type_sector_and_next_step(
    database, admin_conn, channel
):
    say(admin_conn, channel, database, "Ana pediu ferias para dezembro xyzcaso1", who=phone())
    llm = FakeCaseLLM(decision(title="Ferias de Ana xyzcaso1"))

    counts = run(database, channel.tenant_id, llm)

    ((demand_id, title, summary, next_step, kind, sector, _, review, _),) = demands_of(
        admin_conn, channel.tenant_id, "xyzcaso1"
    )
    assert counts["created"] == 1
    assert (title, kind, sector, review) == ("Ferias de Ana xyzcaso1", "nota", "rh-interno", False)
    assert next_step == "Lancar as ferias no sistema de RH."
    assert linked(admin_conn, demand_id) == 1
    ((actor, event_kind, _),) = events_of(admin_conn, demand_id)
    assert (actor, event_kind) == ("ai", "created")


def test_a_follow_up_joins_the_open_case_and_refreshes_the_summary(database, admin_conn, channel):
    who = phone()
    say(admin_conn, channel, database, "Reuniao do projeto IE xyzcaso2", who=who, minutes=0)
    run(
        database,
        channel.tenant_id,
        FakeCaseLLM(decision(title="Projeto IE xyzcaso2", kind="tarefa")),
    )
    say(admin_conn, channel, database, "Tem que incluir o balanco tambem", who=who, minutes=5)
    llm = FakeCaseLLM(
        decision(
            action="attach",
            case_ref=1,
            urgency="alta",
            summary="Projeto IE inclui o balanco xyzcaso2",
            next_step="Preparar o balanco",
        )
    )

    counts = run(database, channel.tenant_id, llm)

    ((demand_id, title, summary, next_step, _, _, urgency, _, _),) = demands_of(
        admin_conn, channel.tenant_id, "xyzcaso2"
    )
    assert counts["attached"] == 1
    assert (summary, next_step, urgency) == (
        "Projeto IE inclui o balanco xyzcaso2",
        "Preparar o balanco",
        "alta",
    )
    assert linked(admin_conn, demand_id) == 2
    assert [kind for _, kind, _ in events_of(admin_conn, demand_id)] == ["created", "attached"]
    sent_ctx = llm.calls[0][1]
    assert [case.title for case in sent_ctx.cases] == ["Projeto IE xyzcaso2"]


def test_an_unsure_match_becomes_a_separate_case_flagged_for_review(database, admin_conn, channel):
    who = phone()
    say(admin_conn, channel, database, "Assunto A xyzcaso3", who=who, minutes=0)
    run(database, channel.tenant_id, FakeCaseLLM(decision(title="Assunto A xyzcaso3")))
    say(admin_conn, channel, database, "Sobre aquilo que falamos xyzcaso3", who=who, minutes=5)
    llm = FakeCaseLLM(
        decision(action="attach", case_ref=1, confidence=0.4, title="Talvez B xyzcaso3")
    )

    counts = run(database, channel.tenant_id, llm)

    cases = demands_of(admin_conn, channel.tenant_id, "xyzcaso3")
    assert counts["review"] == 1 and len(cases) == 2
    flagged = next(case for case in cases if case[1] == "Talvez B xyzcaso3")
    assert flagged[7] is True and "agrupamento" in flagged[8]
    event = next(e for e in events_of(admin_conn, flagged[0]) if e[1] == "review")
    assert event[2]["candidate"] == str(cases[0][0])


def test_the_ai_only_sees_the_open_cases_of_the_same_contact(database, admin_conn, channel):
    first, second = phone(), phone()
    say(admin_conn, channel, database, "Pedido da primeira xyzcaso4", who=first, minutes=0)
    run(database, channel.tenant_id, FakeCaseLLM(decision(title="Caso da primeira xyzcaso4")))
    say(admin_conn, channel, database, "Pedido da segunda xyzcaso4", who=second, minutes=5)
    llm = FakeCaseLLM(decision(title="Caso da segunda xyzcaso4"))

    run(database, channel.tenant_id, llm)

    assert llm.calls[0][1].cases == ()


def test_an_ai_ref_to_a_case_that_closed_meanwhile_opens_a_new_one(database, admin_conn, channel):
    who = phone()
    say(admin_conn, channel, database, "Primeiro xyzcaso5", who=who, minutes=0)
    run(database, channel.tenant_id, FakeCaseLLM(decision(title="Aberto xyzcaso5")))
    say(admin_conn, channel, database, "Segundo xyzcaso5", who=who, minutes=5)

    class ClosingLLM(FakeCaseLLM):
        def analyze(self, text, ctx):
            admin_conn.execute(
                "UPDATE demands SET status = 'concluido', closed_at = now() "
                "WHERE title = 'Aberto xyzcaso5'"
            )
            return super().analyze(text, ctx)

    run(
        database,
        channel.tenant_id,
        ClosingLLM(decision(action="attach", case_ref=1, title="Novo xyzcaso5")),
    )

    cases = demands_of(admin_conn, channel.tenant_id, "xyzcaso5")
    assert len(cases) == 2


def test_ignored_small_talk_is_recorded_and_makes_no_card(database, admin_conn, channel):
    say(admin_conn, channel, database, "Vamos ver isso depois xyzcaso6", who=phone())

    counts = run(
        database, channel.tenant_id, FakeCaseLLM(decision(action="ignore", confidence=0.95))
    )

    assert counts["ignored"] == 1
    assert demands_of(admin_conn, channel.tenant_id, "xyzcaso6") == []


def test_an_unsure_ignore_falls_back_so_a_request_is_never_hidden(database, admin_conn, channel):
    say(admin_conn, channel, database, "Pode ver aquilo xyzcaso7", who=phone())

    counts = run(
        database, channel.tenant_id, FakeCaseLLM(decision(action="ignore", confidence=0.3))
    )

    assert counts["fallback"] == 1
    assert len(demands_of(admin_conn, channel.tenant_id, "xyzcaso7")) == 1


def test_when_the_ai_fails_or_is_off_the_old_rules_still_make_a_card(database, admin_conn, channel):
    say(admin_conn, channel, database, "Preciso da guia xyzcaso8", who=phone(), minutes=0)
    say(admin_conn, channel, database, "Preciso da folha xyzcaso9", who=phone(), minutes=1)

    broken = run(database, channel.tenant_id, FakeCaseLLM(error=ClassifierUnavailable("fora")))
    off = run(database, channel.tenant_id, None)

    assert broken["fallback"] >= 1 and off["created"] + off["attached"] >= 0
    assert len(demands_of(admin_conn, channel.tenant_id, "xyzcaso8")) == 1
    assert len(demands_of(admin_conn, channel.tenant_id, "xyzcaso9")) == 1


def test_an_invalid_answer_also_falls_back(database, admin_conn, channel):
    say(admin_conn, channel, database, "Preciso do alvara xyzcaso10", who=phone())

    counts = run(database, channel.tenant_id, FakeCaseLLM(error=ValueError("fora do contrato")))

    assert counts["fallback"] == 1
    assert len(demands_of(admin_conn, channel.tenant_id, "xyzcaso10")) == 1


def test_the_daily_cap_stops_calling_the_ai(database, admin_conn, channel):
    say(admin_conn, channel, database, "Pedido um xyzcaso11", who=phone(), minutes=0)
    say(admin_conn, channel, database, "Pedido dois xyzcaso11", who=phone(), minutes=1)
    llm = FakeCaseLLM(decision(title="Gerado pela IA xyzcaso11"))

    counts = run(database, channel.tenant_id, llm, daily_cap=1)

    assert len(llm.calls) == 1
    assert counts["created"] == 1 and counts["fallback"] == 1


def test_running_twice_does_not_repeat_anything(database, admin_conn, channel):
    say(admin_conn, channel, database, "Ana pediu ferias xyzcaso12", who=phone())
    llm = FakeCaseLLM(decision(title="Ferias xyzcaso12"))

    run(database, channel.tenant_id, llm)
    again = run(database, channel.tenant_id, llm)

    assert sum(again.values()) == 0
    assert len(demands_of(admin_conn, channel.tenant_id, "xyzcaso12")) == 1
