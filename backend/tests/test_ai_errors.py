import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app import cli
from app.agent.nl.llm import IntentContext, OpenRouterIntentLLM
from app.cases.llm import OpenRouterCaseLLM
from app.cases.prompt import CaseContext
from app.classification.domain import Context
from app.classification.llm import ClassifierUnavailable
from app.classification.openrouter import OpenRouterClassifier, describe_http_error

NOW = datetime(2026, 10, 26, 9, tzinfo=ZoneInfo("America/Sao_Paulo"))
KEY = "sk-or-segredo-de-teste-123"


def refusing(message="Invalid schema: unsupported keyword"):
    body = json.dumps({"error": {"message": message, "code": 400}}).encode()
    return lambda url, headers, payload, timeout: (400, body)


def test_the_error_text_carries_the_providers_reason_without_the_key():
    text = describe_http_error(400, b'{"error": {"message": "Invalid schema   here"}}')

    assert "HTTP 400" in text and "Invalid schema here" in text
    assert len(describe_http_error(500, b"x" * 5000)) < 400
    assert "HTTP 502" in describe_http_error(502, b"")


@pytest.mark.parametrize(
    "call",
    [
        lambda post: OpenRouterClassifier(api_key=KEY, post=post).classify("oi", Context(), {}),
        lambda post: OpenRouterCaseLLM(api_key=KEY, post=post).analyze(
            "oi", CaseContext(None, None, NOW, (), ())
        ),
        lambda post: OpenRouterIntentLLM(api_key=KEY, post=post).understand(
            "oi", IntentContext(NOW, ())
        ),
    ],
)
def test_every_adapter_reports_why_the_provider_refused(call):
    with pytest.raises(ClassifierUnavailable) as caught:
        call(refusing())

    assert "HTTP 400" in str(caught.value) and "unsupported keyword" in str(caught.value)
    assert KEY not in str(caught.value)


class OkIntent:
    model = "m"

    def understand(self, text, ctx):
        from app.agent.nl.contract import parse_intent

        return parse_intent({"intent": "summary", "confidence": 0.9})


class BrokenIntent:
    model = "m"

    def understand(self, text, ctx):
        raise ClassifierUnavailable("OpenRouter respondeu HTTP 400: schema invalido")


class OkCase:
    model = "m"

    def analyze(self, text, ctx):
        from app.cases.contract import parse_case_output

        return parse_case_output(
            {
                "action": "new",
                "case_ref": None,
                "confidence": 0.9,
                "kind": "tarefa",
                "sector": "fiscal",
                "urgency": "normal",
                "title": "T",
                "summary": "S",
                "next_step": None,
                "when_phrase": None,
                "appointment_ref": None,
                "reason": "r",
            },
            open_cases=0,
            appointments=0,
        )


class OkClassifier:
    model = "m"

    def classify(self, text, context, hints):
        from app.classification.domain import LLMOutput

        return LLMOutput("fiscal", "duvida", "normal", None, 0.9, False)


def run_check(monkeypatch, capsys, *, intent, case=None, classifier=None):
    case = case or OkCase()
    classifier = classifier or OkClassifier()
    monkeypatch.setattr(cli, "build_intent_llm", lambda env: (intent, "nota"))
    monkeypatch.setattr(cli, "build_case_llm", lambda env: (case, "nota"))
    monkeypatch.setattr(cli, "build_classifier", lambda env: (classifier, "nota"))
    code = cli.main(["ai-check"])
    return code, capsys.readouterr().out


def test_ai_check_reports_each_ai_and_the_real_error(monkeypatch, capsys):
    code, out = run_check(monkeypatch, capsys, intent=BrokenIntent())

    assert code == 1
    assert "classificacao: ok" in out and "casos: ok" in out
    assert "agente (linguagem natural): FALHOU" in out and "schema invalido" in out


def test_ai_check_passes_when_all_three_work_and_says_when_one_is_off(monkeypatch, capsys):
    code, out = run_check(monkeypatch, capsys, intent=OkIntent())
    assert code == 0 and "agente (linguagem natural): ok" in out and "summary" in out

    code, out = run_check(monkeypatch, capsys, intent=None)
    assert code == 1 and "agente (linguagem natural): desligada" in out


def test_anything_that_looks_like_a_key_is_hidden_from_the_error_text():
    text = describe_http_error(
        401, b'{"error": {"message": "bad key sk-or-v1-abc123XYZ and Bearer tok_9f"}}'
    )

    assert "sk-or-v1-abc123XYZ" not in text and "tok_9f" not in text
    assert "[chave]" in text and "HTTP 401" in text
