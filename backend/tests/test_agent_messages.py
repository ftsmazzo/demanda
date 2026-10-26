from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.agent.messages import (
    AppointmentInfo,
    StuckItem,
    SummaryData,
    appointment_text,
    stuck_text,
    summary_text,
)

SP = ZoneInfo("America/Sao_Paulo")
URL = "https://demanda.exemplo.com"


def test_an_appointment_alert_says_who_what_when_and_where_to_answer():
    info = AppointmentInfo(
        title="Vamos marcar uma reuniao para definir o projeto IE",
        starts_at=datetime(2026, 10, 28, 14, 0, tzinfo=SP),
        all_day=False,
        contact_name="Poli",
        sector="Societario",
    )

    text = appointment_text(info, URL)

    assert "Poli" in text
    assert "quarta-feira, 28/10 às 14:00" in text
    assert "definir o projeto IE" in text
    assert f"{URL}/agenda" in text


def test_an_all_day_appointment_has_no_clock_and_a_missing_contact_is_not_invented():
    info = AppointmentInfo("Visita", datetime(2026, 10, 29, tzinfo=SP), True, None, "Fiscal")

    text = appointment_text(info, URL)

    assert "o dia todo" in text
    assert "None" not in text
    assert "00:00" not in text


def test_the_daily_summary_has_the_numbers_the_stuck_ones_and_tomorrow():
    data = SummaryData(
        day=date(2026, 10, 26),
        created_today=3,
        closed_today=2,
        open_total=12,
        critical_open=2,
        stuck=[StuckItem("Certidao negativa", "Societario", 96), StuckItem("Folha", "Pessoal", 30)],
        tomorrow=[("14:00", "Reuniao do projeto IE")],
    )

    text = summary_text(data, URL)

    assert "segunda-feira, 26/10" in text
    assert "3 novas" in text and "2 concluídas" in text
    assert "12 abertas" in text and "2 críticas" in text
    assert "Certidao negativa" in text and "4 dias" in text
    assert "Folha (Pessoal, 1 dia)" in text
    assert "14:00 Reuniao do projeto IE" in text
    assert f"{URL}/" in text


def test_a_quiet_summary_leaves_out_empty_sections():
    data = SummaryData(date(2026, 10, 26), 0, 1, 4, 0, [], [])

    text = summary_text(data, URL)

    assert "Mais paradas" not in text
    assert "Amanhã" not in text
    assert "críticas" not in text


def test_the_stuck_alert_lists_the_longest_waiting_first_with_how_long():
    items = [StuckItem("A", "Fiscal", 100), StuckItem("B", "Pessoal", 75)]

    text = stuck_text(items, URL)

    assert text.index("A") < text.index("B")
    assert "4 dias" in text and "3 dias" in text
    assert f"{URL}/" in text
