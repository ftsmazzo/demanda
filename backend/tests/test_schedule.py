from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.core.schedule import extract_when

SP = ZoneInfo("America/Sao_Paulo")
# domingo, 25/10/2026, meio-dia em Sao Paulo
REF = datetime(2026, 10, 25, 12, 0, tzinfo=SP)


def at(month, day, hour=0, minute=0, year=2026):
    return datetime(year, month, day, hour, minute, tzinfo=SP)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Vamos marcar uma reunião Quarta feira às 14 para definir o projeto IE", at(10, 28, 14)),
        ("amanhã às 9h30 na sala de reunião", at(10, 26, 9, 30)),
        ("Amanha as 9:30", at(10, 26, 9, 30)),
        ("depois de amanhã 8:15", at(10, 27, 8, 15)),
        ("hoje às 16h", at(10, 25, 16)),
        ("dia 28 às 10h", at(10, 28, 10)),
        ("dia 20 às 10h", at(11, 20, 10)),
        ("28/10 às 15:00", at(10, 28, 15)),
        ("05/01 às 9h", at(1, 5, 9, year=2027)),
        ("28/10/2026 às 15h", at(10, 28, 15)),
        ("dia 5 de novembro às 14h", at(11, 5, 14)),
        ("segunda às 8", at(10, 26, 8)),
        ("domingo às 10", at(11, 1, 10)),
        ("sexta que vem às 11h", at(10, 30, 11)),
        ("próxima terça 9h", at(10, 27, 9)),
        ("terça-feira às 14 horas", at(10, 27, 14)),
        ("sábado ao meio dia", at(10, 31, 12)),
        ("quinta, meio-dia", at(10, 29, 12)),
    ],
)
def test_it_reads_day_and_time_in_portuguese(text, expected):
    found = extract_when(text, REF)

    assert found is not None
    assert found.start == expected
    assert found.all_day is False


def test_a_day_without_time_is_an_all_day_event():
    found = extract_when("reunião na quarta", REF)

    assert found is not None
    assert found.all_day is True
    assert found.start == at(10, 28)


@pytest.mark.parametrize(
    "text",
    [
        "Preciso marcar uma reunião",
        "às 14 por favor",
        "dia 32 às 10h",
        "amanhã às 25h",
        "Pode mandar a segunda via do boleto?",
        "",
        "Bom dia, tudo bem?",
    ],
)
def test_it_gives_up_when_there_is_no_usable_date(text):
    assert extract_when(text, REF) is None


def test_the_reference_time_zone_decides_the_clock():
    utc_ref = datetime(2026, 10, 25, 15, 0, tzinfo=ZoneInfo("UTC"))  # 12:00 em Sao Paulo

    found = extract_when("amanhã às 9h", utc_ref.astimezone(SP))

    assert found is not None and found.start.utcoffset().total_seconds() == -3 * 3600
