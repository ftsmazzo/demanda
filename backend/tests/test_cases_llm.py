import json
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.cases.contract import OUTPUT_SCHEMA
from app.cases.llm import AnthropicCaseLLM, OpenRouterCaseLLM, build_case_llm
from app.cases.prompt import CaseContext
from app.classification.llm import ClassifierUnavailable

KEY = "sk-or-chave-secreta-de-teste"
NOW = datetime(2026, 10, 26, 9, tzinfo=ZoneInfo("America/Sao_Paulo"))
CTX = CaseContext(None, "cliente", NOW, (), ())
VALID = {
    "action": "new",
    "case_ref": None,
    "confidence": 0.9,
    "kind": "nota",
    "sector": "rh-interno",
    "urgency": "normal",
    "title": "Ferias de Ana",
    "summary": "Ana pediu ferias.",
    "next_step": "Lancar as ferias.",
    "when_phrase": None,
    "appointment_ref": None,
    "reason": "assunto novo",
}


class FakePost:
    def __init__(self, status=200, payload=None, error=None):
        self.status, self.payload, self.error = status, payload, error
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, headers, json.loads(body), timeout))
        if self.error:
            raise self.error
        raw = self.payload if isinstance(self.payload, bytes) else json.dumps(self.payload).encode()
        return self.status, raw


def answer(content, finish_reason="stop"):
    text = content if isinstance(content, str) else json.dumps(content)
    return {"choices": [{"message": {"content": text}, "finish_reason": finish_reason}]}


def analyze(post, text="Ana pediu ferias"):
    return OpenRouterCaseLLM(api_key=KEY, post=post).analyze(text, CTX)


def test_a_valid_answer_becomes_a_decision():
    decision = analyze(FakePost(payload=answer(VALID)))

    assert (decision.action, decision.sector, decision.kind) == ("new", "rh-interno", "nota")


def test_the_request_asks_for_the_strict_schema_and_sends_the_prompt():
    post = FakePost(payload=answer(VALID))

    analyze(post, "Ana pediu ferias")

    _, headers, body, _ = post.calls[0]
    assert headers["Authorization"] == f"Bearer {KEY}"
    assert body["response_format"]["json_schema"]["schema"] == OUTPUT_SCHEMA
    assert body["provider"] == {"require_parameters": True}
    assert body["messages"][0]["role"] == "system"
    assert "<mensagem>\nAna pediu ferias\n</mensagem>" in body["messages"][1]["content"]


def test_fenced_json_is_accepted():
    fenced = "```json\n" + json.dumps(VALID) + "\n```"

    assert analyze(FakePost(payload=answer(fenced))).title == "Ferias de Ana"


@pytest.mark.parametrize(
    "post",
    [
        FakePost(status=500, payload={}),
        FakePost(error=OSError("rede")),
        FakePost(payload={"error": {"code": 429}}),
    ],
)
def test_service_problems_are_reported_as_unavailable(post):
    with pytest.raises(ClassifierUnavailable):
        analyze(post)


@pytest.mark.parametrize(
    "payload",
    [
        answer("isto nao e json"),
        answer(VALID, finish_reason="length"),
        answer({**VALID, "kind": "ferias"}),
        {"choices": []},
    ],
)
def test_malformed_or_off_contract_answers_raise_value_error(payload):
    with pytest.raises(ValueError):
        analyze(FakePost(payload=payload))


def test_the_anthropic_adapter_parses_the_structured_text():
    block = SimpleNamespace(type="text", text=json.dumps(VALID))
    response = SimpleNamespace(stop_reason="end_turn", content=[block])
    client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))

    decision = AnthropicCaseLLM(client=client).analyze("Ana pediu ferias", CTX)

    assert decision.title == "Ferias de Ana"


def test_the_factory_follows_the_environment():
    assert build_case_llm({})[0] is None
    assert build_case_llm({"CASE_LLM": "off", "OPENROUTER_API_KEY": KEY})[0] is None
    llm, note = build_case_llm({"OPENROUTER_API_KEY": KEY})
    assert isinstance(llm, OpenRouterCaseLLM) and "OpenRouter" in note
    assert KEY not in note
    assert isinstance(build_case_llm({"ANTHROPIC_API_KEY": "x"})[0], AnthropicCaseLLM)
