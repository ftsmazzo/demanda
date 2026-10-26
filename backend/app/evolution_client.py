"""Cliente minimo da Evolution API v2 (so leitura): estado da instancia e historico de mensagens."""

import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import datetime
from typing import Any
from urllib.parse import quote

TIMEOUT_SECONDS = 10
PAGE_SIZE = 50
_INSTANCE = re.compile(r"^[A-Za-z0-9_-][A-Za-z0-9_.-]{0,99}$")

Transport = Callable[[str, str, dict[str, str], bytes | None], tuple[int, Any]]


class EvolutionError(Exception):
    """A Evolution nao respondeu como esperado."""


def _urllib_transport(
    method: str, url: str, headers: dict[str, str], body: bytes | None
) -> tuple[int, Any]:
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        return exc.code, None


class EvolutionClient:
    def __init__(self, base_url: str, api_key: str, *, transport: Transport | None = None) -> None:
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._transport = transport or _urllib_transport

    def _call(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        ok: tuple[int, ...] = (200,),
    ) -> Any:
        headers = {"apikey": self._key, "Content-Type": "application/json"}
        body = json.dumps(payload).encode() if payload is not None else None
        status, data = self._transport(method, f"{self._base}{path}", headers, body)
        if status not in ok:
            raise EvolutionError(f"Evolution respondeu HTTP {status}")
        return data

    def connection_state(self, instance: str) -> str:
        """open, close, connecting, unknown (sem estado) ou unreachable (nao respondeu)."""
        if not _INSTANCE.match(instance):
            return "unreachable"
        try:
            data = self._call("GET", f"/instance/connectionState/{quote(instance)}")
        except (EvolutionError, OSError, ValueError):
            return "unreachable"
        state = (data or {}).get("instance", {}).get("state") if isinstance(data, dict) else None
        return state if isinstance(state, str) and state else "unknown"

    def find_messages(
        self,
        instance: str,
        *,
        since: datetime,
        until: datetime,
        page: int = 1,
        offset: int = PAGE_SIZE,
    ) -> tuple[list[dict[str, Any]], int]:
        """Mensagens da janela, mais recentes primeiro. Devolve (registros, total de paginas)."""
        if not _INSTANCE.match(instance):
            raise EvolutionError("nome de instancia invalido")
        payload = {
            "where": {"messageTimestamp": {"gte": since.isoformat(), "lte": until.isoformat()}},
            "page": page,
            "offset": offset,
        }
        try:
            data = self._call("POST", f"/chat/findMessages/{quote(instance)}", payload)
        except (OSError, ValueError) as exc:
            raise EvolutionError("falha de rede ao falar com a Evolution") from exc
        block = data.get("messages") if isinstance(data, dict) else None
        if not isinstance(block, dict) or not isinstance(block.get("records"), list):
            raise EvolutionError("resposta inesperada da Evolution")
        return block["records"], int(block.get("pages") or 1)

    def send_text(self, instance: str, number: str, text: str) -> None:
        """Envia um texto pela instancia do agente (POST /message/sendText/{instancia})."""
        if not _INSTANCE.match(instance):
            raise EvolutionError("nome de instancia invalido")
        try:
            self._call(
                "POST",
                f"/message/sendText/{quote(instance)}",
                {"number": number, "text": text},
                ok=(200, 201),
            )
        except (OSError, ValueError) as exc:
            raise EvolutionError("falha de rede ao falar com a Evolution") from exc
