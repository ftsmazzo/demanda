"""Classificador por IA via OpenRouter (API compativel com chat completions)."""

import json
import logging
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from app.classification.domain import Context, LLMOutput
from app.classification.llm import (
    OUTPUT_SCHEMA,
    SYSTEM_PROMPT,
    ClassifierUnavailable,
    build_user_prompt,
    parse_llm_output,
)

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "anthropic/claude-haiku-5.5"
REQUEST_TIMEOUT_SECONDS = 25

PostFn = Callable[[str, dict[str, str], bytes, float], tuple[int, bytes]]

_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.S)


def _urllib_post(
    url: str, headers: dict[str, str], body: bytes, timeout: float
) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


class OpenRouterClassifier:
    def __init__(
        self,
        api_key: str,
        model: str | None = None,
        post: PostFn | None = None,
        url: str = OPENROUTER_URL,
    ) -> None:
        self._api_key = api_key
        self._model = model or os.environ.get("CLASSIFIER_MODEL", DEFAULT_MODEL)
        self._post = post or _urllib_post
        self._url = url

    @property
    def model(self) -> str:
        return self._model

    def classify(self, text: str, context: Context, hints: dict[str, Any]) -> LLMOutput:
        body = json.dumps(
            {
                "model": self._model,
                "max_tokens": 1024,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(text, context, hints)},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "classificacao",
                        "strict": True,
                        "schema": OUTPUT_SCHEMA,
                    },
                },
                # so roteia para provedores que respeitam o schema
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
            code = payload["error"].get("code") if isinstance(payload["error"], dict) else None
            raise ClassifierUnavailable(f"OpenRouter devolveu erro (codigo {code})")

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("resposta do OpenRouter sem choices")
        choice = choices[0]
        if choice.get("finish_reason") == "length":
            raise ValueError("resposta da IA cortada por tamanho")
        content = (choice.get("message") or {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("resposta da IA sem conteudo")
        fenced = _FENCE.match(content.strip())
        try:
            data = json.loads(fenced.group(1) if fenced else content)
        except json.JSONDecodeError as exc:
            raise ValueError("resposta da IA nao e JSON") from exc
        return parse_llm_output(data)
