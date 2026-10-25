import pytest

from app.classification.domain import Context
from app.classification.rules import classify_by_rules, normalize


def rules(text, **ctx):
    return classify_by_rules(text, Context(**ctx))


CASES = [
    (
        "Segue as notas fiscais do mes pra fechar",
        {"has_media": True},
        "fiscal",
        "documento",
        "normal",
    ),
    ("Quando vence o DAS esse mes?", {}, "fiscal", "duvida", "normal"),
    ("Preciso da folha de pagamento de outubro", {}, "dp", "tarefa", "normal"),
    (
        "Quinta as 15h da pra falar sobre a abertura da filial?",
        {},
        "societario",
        "compromisso",
        "normal",
    ),
    (
        "Segue boleto da internet, vence dia 10",
        {"contact_type": "fornecedor"},
        "financeiro",
        "cobranca",
        "normal",
    ),
    (
        "Ja pedi 3 vezes a certidao negativa, ninguem me responde!!",
        {},
        "societario",
        "reclamacao",
        "critica",
    ),
    (
        "Preciso de folga dia 30, posso?",
        {"contact_type": "colaborador"},
        "rh-interno",
        "tarefa",
        "normal",
    ),
    ("Urgente: preciso da guia do DAS hoje", {}, "fiscal", "tarefa", "alta"),
    ("Rescisão do funcionário João, pode calcular?", {}, "dp", "tarefa", "normal"),
]


@pytest.mark.parametrize(("text", "ctx", "sector", "kind", "urgency"), CASES)
def test_rules_resolve_sector_kind_and_urgency(text, ctx, sector, kind, urgency):
    result = rules(text, **ctx)

    assert (result.sector, result.kind, result.urgency) == (sector, kind, urgency)
    assert result.complete


def test_tie_between_sectors_is_left_unresolved():
    result = rules("Preciso do balancete e da guia")

    assert result.sector is None
    assert not result.complete


def test_text_without_keywords_is_unresolved():
    result = rules("Pode me ajudar com uma coisa aqui?")

    assert result.sector is None
    assert not result.complete
    assert not result.noise


@pytest.mark.parametrize("text", ["Bom dia!", "obrigado", "Valeu, boa tarde", "ok"])
def test_greetings_and_thanks_without_open_demand_are_noise(text):
    result = rules(text)

    assert result.noise
    assert not result.attach_reply


@pytest.mark.parametrize("text", ["ok", "Pode ser", "fechado", "Combinado!", "obrigado"])
def test_short_acknowledgement_with_open_demand_attaches_to_it(text):
    result = rules(text, has_open_demand=True)

    assert result.attach_reply
    assert not result.noise


def test_a_real_request_is_never_noise_even_if_it_starts_with_a_greeting():
    result = rules("Bom dia, preciso da guia do DAS", has_open_demand=True)

    assert not result.noise
    assert not result.attach_reply
    assert result.sector == "fiscal"


def test_normalize_strips_accents_case_and_extra_spaces():
    assert normalize("  RESCISÃO   do  FUNCIONÁRIO ") == "rescisao do funcionario"


REGRESSIONS = [
    ("Quero saber quando sai o holerite", {}, "dp", "duvida", "normal"),
    (
        "Fiz a alteração contratual, podem registrar na junta comercial?",
        {},
        "societario",
        "tarefa",
        "normal",
    ),
    ("Péssimo atendimento, vou trocar de contabilidade", {}, None, "reclamacao", "alta"),
    (
        "Estou esperando faz uma semana e ninguém retorna, isso é um absurdo",
        {},
        None,
        "reclamacao",
        "alta",
    ),
    (
        "Queria trocar a folga de sexta pela de sábado",
        {"contact_type": "colaborador"},
        "rh-interno",
        "tarefa",
        "normal",
    ),
    (
        "Vou precisar me afastar semana que vem",
        {"contact_type": "colaborador"},
        "rh-interno",
        "tarefa",
        "normal",
    ),
    (
        "não consegui acessar o portal da prefeitura pra emitir nota",
        {},
        "fiscal",
        "tarefa",
        "normal",
    ),
    ("Preciso do cálculo de 13º salário", {}, "dp", "tarefa", "normal"),
    ("Recebi uma multa da Receita, o que faço?", {}, "fiscal", "duvida", "critica"),
    ("Mandei as NFs de entrada ontem, conseguiram lançar?", {}, "fiscal", "duvida", "normal"),
]


@pytest.mark.parametrize(("text", "ctx", "sector", "kind", "urgency"), REGRESSIONS)
def test_regressions_found_by_the_golden_set(text, ctx, sector, kind, urgency):
    result = rules(text, **ctx)

    assert (result.sector, result.kind, result.urgency) == (sector, kind, urgency)


def test_how_long_it_takes_is_a_question_not_a_complaint():
    assert rules("Quanto tempo demora para abrir uma empresa?").kind == "duvida"


def test_the_word_contabilidade_alone_does_not_pick_a_sector():
    assert rules("Gostaria de falar sobre a contabilidade").sector is None


@pytest.mark.parametrize(
    "text",
    [
        "Qual o valor das contas desse mes?",
        "Por essa razão eu liguei",
        "Vocês têm um jeito simples de fazer isso?",
        "Dei nota 10 para o atendimento",
    ],
)
def test_common_words_do_not_pick_a_sector(text):
    assert rules(text).sector is None


def test_uppercase_das_or_guia_do_das_still_means_fiscal():
    assert rules("Preciso pagar o DAS").sector == "fiscal"
    assert rules("preciso da guia do das").sector == "fiscal"


def test_business_hours_question_is_not_an_appointment():
    assert rules("Qual o horário de funcionamento do escritório?").kind == "duvida"


def test_cancelling_a_meeting_is_not_a_complaint():
    result = rules("Vou cancelar a reunião de quinta")

    assert result.kind == "compromisso"
    assert result.urgency == "normal"


def test_threatening_to_leave_the_firm_is_a_complaint():
    assert rules("Vou cancelar o contrato com vocês").kind == "reclamacao"


def test_punctuation_only_message_is_noise():
    assert rules("!!!").noise
