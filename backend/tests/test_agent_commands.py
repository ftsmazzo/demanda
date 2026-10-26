import pytest

from app.agent.commands import parse_command


@pytest.mark.parametrize(
    "text",
    ["1", " 1 ", "Confirmar", "confirma", "CONFIRMO!", "sim", "Sim, pode confirmar", "confirmado"],
)
def test_confirmations(text):
    assert parse_command(text) == "confirm"


@pytest.mark.parametrize("text", ["2", "Cancelar", "cancela", "Cancelo.", "cancelado"])
def test_cancellations(text):
    assert parse_command(text) == "cancel"


@pytest.mark.parametrize(
    "text",
    [
        "O que está parado?",
        "pendências",
        "Pendencias",
        "o que ta parado no fiscal",
        "quais estão atrasadas",
    ],
)
def test_asking_what_is_stuck(text):
    assert parse_command(text) == "stuck"


@pytest.mark.parametrize(
    "text", ["agenda", "Agenda de hoje", "o que tenho amanhã?", "compromissos"]
)
def test_asking_for_the_agenda(text):
    assert parse_command(text) == "agenda"


@pytest.mark.parametrize("text", ["ajuda", "Menu", "?", "oi", "Olá", "bom dia", "help"])
def test_help_and_greetings(text):
    assert parse_command(text) == "help"


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "talvez",
        "ok",
        "não",
        "quero confirmar a reunião de quarta com a Poli",
        "12",
        "10",
    ],
)
def test_anything_else_is_unknown_so_it_never_acts_by_accident(text):
    assert parse_command(text) == "unknown"
