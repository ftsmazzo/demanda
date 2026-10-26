import pytest
from psycopg import errors

from tests.test_api_visibility import new_demand


def test_a_demand_can_carry_a_summary_a_next_step_and_the_note_kind(admin_conn, tenant_id):
    demand = new_demand(admin_conn, tenant_id, kind="nota")

    admin_conn.execute(
        "UPDATE demands SET summary = 'Resumo', next_step = 'Lancar', needs_review = true, "
        "review_reason = 'confirmar agrupamento', ai_updated_at = now() WHERE id = %s",
        (demand,),
    )

    row = admin_conn.execute(
        "SELECT kind, summary, next_step, needs_review FROM demands WHERE id = %s", (demand,)
    ).fetchone()
    assert row == ("nota", "Resumo", "Lancar", True)


def test_case_events_record_who_changed_what_and_reject_unknown_values(admin_conn, tenant_id):
    demand = new_demand(admin_conn, tenant_id)
    admin_conn.execute(
        "INSERT INTO case_events (tenant_id, demand_id, actor, kind, data) "
        'VALUES (%s, %s, \'ai\', \'summary\', \'{"antes": "a", "depois": "b"}\')',
        (tenant_id, demand),
    )

    with pytest.raises(errors.CheckViolation):
        admin_conn.execute(
            "INSERT INTO case_events (tenant_id, demand_id, actor, kind) "
            "VALUES (%s, %s, 'robot', 'summary')",
            (tenant_id, demand),
        )


def test_case_events_are_isolated_between_tenants(database, admin_conn, tenant_id, other_channel):
    demand = new_demand(admin_conn, tenant_id)
    admin_conn.execute(
        "INSERT INTO case_events (tenant_id, demand_id, actor, kind) "
        "VALUES (%s, %s, 'rules', 'created')",
        (tenant_id, demand),
    )

    with database.tenant_transaction(other_channel.tenant_id) as conn:
        seen = conn.execute("SELECT count(*) FROM case_events").fetchone()[0]
    with database.tenant_transaction(tenant_id) as conn:
        mine = conn.execute("SELECT count(*) FROM case_events").fetchone()[0]

    assert seen == 0 and mine >= 1
