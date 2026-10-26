"""Adaptadores da IA de caso (OpenRouter e Anthropic), com saida estruturada e validacao."""

import json
import os
import re
import urllib.error
from collections.abc import Mapping
from typing import Any, Protocol

import anthropic

from app.cases.contract import OUTPUT_SCHEMA, CaseDecision, parse_case_output
from app.cases.prompt import SYSTEM_PROMPT, CaseContext, build_user_prompt
from app.classification.llm import ClassifierUnavailable
from app.classification.openrouter import OPENROUTER_URL, PostFn, _urllib_post

DEFAULT_OPENROUTER_MODEL = "anthropic/claude-haiku-5.5"
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-5-5"
REQUEST_TIMEOUT_SECONDS = 30

_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.S)


class CaseLLM(Protocol):
    def analyze(self, text: str, ctx: CaseContext) -> CaseDecision: ...


def _decision(data: Any, ctx: CaseContext) -> CaseDecision:
    return parse_case_output(data, open_cases=len(ctx.cases), appointments=len(ctx.appointments))


class OpenRouterCaseLLM:
    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        post: PostFn | None = None,
        url: str = OPENROUTER_URL,
    ) -> None:
        self._api_key = api_key
        self._model = model or os.environ.get("CASE_MODEL", DEFAULT_OPENROUTER_MODEL)
        self._post = post or _urllib_post
        self._url = url

    @property
    def model(self) -> str:
        return self._model

    def analyze(self, text: str, ctx: CaseContext) -> CaseDecision:
        body = json.dumps(
            {
                "model": self._model,
                "max_tokens": 1024,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(text, ctx)},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "caso", "strict": True, "schema": OUTPUT_SCHEMA},
                },
                "provider": {"require_parameters": True},
            }
        ).encode()
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-Title": "Demanda",
        }
        try:
            status, raw = self._post(self._url, headers, body, REQUEST_TIMEOUT_SECONDS)
        except (OSError, urllib.error.URLError) as exc:
            raise ClassifierUnavailable(f"falha de rede: {type(exc).__name__}") from exc
        if status != 200:
            raise ClassifierUnavailable(f"OpenRouter respondeu HTTP {status}")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("resposta do OpenRouter nao e JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("resposta do OpenRouter inesperada")
        if payload.get("error"):
            raise ClassifierUnavailable("OpenRouter devolveu erro")
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("resposta do OpenRouter sem choices")
        if choices[0].get("finish_reason") == "length":
            raise ValueError("resposta da IA cortada por tamanho")
        content = (choices[0].get("message") or {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("resposta da IA sem conteudo")
        fenced = _FENCE.match(content.strip())
        try:
            data = json.loads(fenced.group(1) if fenced else content)
        except json.JSONDecodeError as exc:
            raise ValueError("resposta da IA nao e JSON") from exc
        return _decision(data, ctx)


class AnthropicCaseLLM:
    def __init__(self, client: Any | None = None, model: str | None = None) -> None:
        self._client = client or anthropic.Anthropic(timeout=30.0, max_retries=2)
        self._model = model or os.environ.get("CASE_MODEL", DEFAULT_ANTHROPIC_MODEL)

    @property
    def model(self) -> str:
        return self._model

    def analyze(self, text: str, ctx: CaseContext) -> CaseDecision:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": build_user_prompt(text, ctx)}],
                output_config={
                    "effort": "low",
                    "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
                },
            )
        except anthropic.APIError as exc:
            raise ClassifierUnavailable(f"erro da API: {type(exc).__name__}") from exc
        if response.stop_reason == "refusal":
            raise ClassifierUnavailable("a IA recusou a solicitacao")
        texts = [block.text for block in response.content if block.type == "text"]
        if not texts:
            raise ValueError("resposta da IA sem texto")
        try:
            data = json.loads(texts[-1])
        except json.JSONDecodeError as exc:
            raise ValueError("resposta da IA nao e JSON") from exc
        return _decision(data, ctx)


def build_case_llm(env: Mapping[str, str]) -> tuple[CaseLLM | None, str]:
    """IA de caso pelo ambiente. CASE_LLM=off desliga; sem chave tambem fica desligada."""
    if (env.get("CASE_LLM") or "").strip().lower() == "off":
        return None, "IA de caso desligada por CASE_LLM=off"
    if env.get("OPENROUTER_API_KEY"):
        llm = OpenRouterCaseLLM(api_key=env["OPENROUTER_API_KEY"])
        return llm, f"IA de caso via OpenRouter, modelo {llm.model}"
    if env.get("ANTHROPIC_API_KEY"):
        llm = AnthropicCaseLLM()
        return llm, f"IA de caso via Anthropic, modelo {llm.model}"
    return None, "IA de caso desligada: sem chave de IA"
