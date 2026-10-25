import threading

from app.worker import BackgroundWorker, run_cycle
from tests.test_classification_store import add_message


def test_a_cycle_classifies_and_opens_demands_for_every_tenant(
    database, admin_conn, channel, other_channel
):
    add_message(admin_conn, channel, "W1", "Quando vence o DAS xyzciclo1?", minutes=700000)
    add_message(admin_conn, other_channel, "W2", "Quando vence o DAS xyzciclo2?", minutes=700000)

    summary = run_cycle(database, llm=None)

    titles = {
        row[0]
        for row in admin_conn.execute(
            "SELECT title FROM demands WHERE title LIKE '%xyzciclo%'"
        ).fetchall()
    }
    assert len(titles) == 2
    assert summary["classified"] >= 2
    assert summary["created"] >= 2


def test_a_second_cycle_has_nothing_left_to_do(database, admin_conn, channel):
    add_message(admin_conn, channel, "W3", "Quando vence o DAS xyzciclo3?", minutes=700001)
    run_cycle(database, llm=None)

    again = run_cycle(database, llm=None)

    count = admin_conn.execute(
        "SELECT count(*) FROM demands WHERE title LIKE '%xyzciclo3%'"
    ).fetchone()[0]
    assert count == 1
    assert again["created"] == 0


def test_the_runtime_role_can_list_tenants_only_through_the_function(database, tenant_id):
    with database._pool.connection() as conn:
        visible = conn.execute("SELECT count(*) FROM tenants").fetchone()[0]

    assert tenant_id in database.tenant_ids()
    assert visible == 0


def test_the_worker_runs_in_the_background_and_stops_cleanly(database, admin_conn, channel):
    add_message(admin_conn, channel, "W4", "Quando vence o DAS xyzciclo4?", minutes=700002)
    done = threading.Event()
    worker = BackgroundWorker(
        database, llm=None, interval_seconds=0.05, on_cycle=lambda _: done.set()
    )

    worker.start()
    assert done.wait(10)
    worker.stop()

    assert not worker.is_alive()
    assert (
        admin_conn.execute(
            "SELECT count(*) FROM demands WHERE title LIKE '%xyzciclo4%'"
        ).fetchone()[0]
        == 1
    )


def test_a_failing_cycle_does_not_kill_the_worker(database):
    calls = []

    class Boom(BackgroundWorker):
        def cycle(self):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("falha de teste")
            return {}

    worker = Boom(database, llm=None, interval_seconds=0.02)
    worker.start()
    for _ in range(200):
        if len(calls) >= 3:
            break
        threading.Event().wait(0.02)
    worker.stop()

    assert len(calls) >= 3


def test_the_app_runs_the_worker_while_it_is_up(admin_url, admin_conn, channel):
    from fastapi.testclient import TestClient

    from app.main import create_app

    add_message(admin_conn, channel, "W5", "Quando vence o DAS xyzciclo5?", minutes=700003)

    with TestClient(create_app(admin_url, worker_interval_seconds=0.05)):
        for _ in range(200):
            found = admin_conn.execute(
                "SELECT count(*) FROM demands WHERE title LIKE '%xyzciclo5%'"
            ).fetchone()[0]
            if found:
                break
            threading.Event().wait(0.05)

    assert found == 1
