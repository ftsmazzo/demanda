from app.cases.service import materialize_cases
from app.classification.store import classify_pending
from app.core.demands import materialize_demands
from tests.agent_helpers import MON_MORNING, FakeSender, add_demand, add_recipient, cycle
from tests.cases_helpers import CLASSIFIER, FakeCaseLLM, decision, phone
from tests.test_classification_store import add_message


def priority_contact(conn, tenant_id, number):
    conn.execute(
        "INSERT INTO contacts (tenant_id, phone, priority) VALUES (%s, %s, true) "
        "ON CONFLICT (tenant_id, phone) DO UPDATE SET priority = true",
        (tenant_id, number),
    )


def urgency_of(conn, tenant_id, marker):
    return conn.execute(
        "SELECT urgency FROM demands WHERE tenant_id = %s AND (title LIKE %s OR summary LIKE %s)",
        (tenant_id, f"%{marker}%", f"%{marker}%"),
    ).fetchone()[0]


def test_a_priority_client_never_gets_a_normal_urgency_from_the_rules(
    database, admin_conn, channel
):
    vip, common = phone(), phone()
    priority_contact(admin_conn, channel.tenant_id, vip)
    add_message(admin_conn, channel, "PE1", "Preciso da guia xyzvip1", phone=vip, minutes=0)
    add_message(admin_conn, channel, "PE2", "Preciso da guia xyzcom1", phone=common, minutes=1)
    classify_pending(database, channel.tenant_id, llm=None)

    materialize_demands(database, channel.tenant_id)

    assert urgency_of(admin_conn, channel.tenant_id, "xyzvip1") == "alta"
    assert urgency_of(admin_conn, channel.tenant_id, "xyzcom1") == "normal"


def test_the_case_ai_path_also_lifts_a_priority_client(database, admin_conn, channel):
    vip = phone()
    priority_contact(admin_conn, channel.tenant_id, vip)
    add_message(admin_conn, channel, "PE3", "Pode ver aquilo xyzvip2", phone=vip, minutes=0)
    classify_pending(database, channel.tenant_id, llm=CLASSIFIER)

    materialize_cases(
        database, channel.tenant_id, FakeCaseLLM(decision(title="Caso xyzvip2", urgency="normal"))
    )

    assert urgency_of(admin_conn, channel.tenant_id, "xyzvip2") == "alta"


def test_a_critical_one_stays_critical(database, admin_conn, channel):
    vip = phone()
    priority_contact(admin_conn, channel.tenant_id, vip)
    add_message(admin_conn, channel, "PE4", "Pode ver aquilo xyzvip3", phone=vip, minutes=0)
    classify_pending(database, channel.tenant_id, llm=CLASSIFIER)

    materialize_cases(
        database, channel.tenant_id, FakeCaseLLM(decision(title="Caso xyzvip3", urgency="critica"))
    )

    assert urgency_of(admin_conn, channel.tenant_id, "xyzvip3") == "critica"


def test_the_stuck_alert_comes_sooner_for_priority_clients_and_says_so(
    database, admin_conn, tenant_id
):
    add_recipient(admin_conn, tenant_id, "5511999990001")
    vip = phone()
    priority_contact(admin_conn, tenant_id, vip)
    contact_id = admin_conn.execute(
        "SELECT id FROM contacts WHERE tenant_id = %s AND phone = %s", (tenant_id, vip)
    ).fetchone()[0]
    now = MON_MORNING
    for title, contact in (("Do prioritario", contact_id), ("Do comum", None)):
        demand = add_demand(admin_conn, tenant_id, title=title, idle_hours=30, now=now)
        admin_conn.execute("UPDATE demands SET contact_id = %s WHERE id = %s", (contact, demand))
    sender = FakeSender()

    cycle(database, tenant_id, sender, now)

    text = sender.sent[0][1]
    assert "Do prioritario" in text and "Do comum" not in text
    assert "prioritário" in text
