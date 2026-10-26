"""Envio das mensagens do agente. Atras de um adaptador: hoje Evolution, amanha a API oficial."""

import re
from collections.abc import Mapping
from typing import Protocol

from app.evolution_client import EvolutionClient, EvolutionError


class SendError(Exception):
    """A mensagem nao foi entregue ao provedor."""


class MessageSender(Protocol):
    mode: str  # estado gravado quando o envio da certo: "sent" ou "dry_run"

    def send(self, phone: str, text: str) -> None: ...


def digits(phone: str) -> str:
    return re.sub(r"\D", "", phone)


class EvolutionSender:
    mode = "sent"

    def __init__(self, client: EvolutionClient, instance: str) -> None:
        self._client = client
        self._instance = instance

    def send(self, phone: str, text: str) -> None:
        try:
            self._client.send_text(self._instance, digits(phone), text)
        except EvolutionError as exc:
            raise SendError(str(exc)) from exc


class DryRunSender:
    """Ensaio: nada sai. O texto fica na caixa de saida para o responsavel conferir."""

    mode = "dry_run"

    def send(self, phone: str, text: str) -> None:
        return None


def build_sender(env: Mapping[str, str], client: EvolutionClient | None) -> MessageSender | None:
    """Sem AGENT_INSTANCE (ou sem Evolution) o agente fica desligado; sem AGENT_SEND=1, ensaio."""
    instance = (env.get("AGENT_INSTANCE") or "").strip()
    if not instance or client is None:
        return None
    if env.get("AGENT_SEND") == "1":
        return EvolutionSender(client, instance)
    return DryRunSender()
