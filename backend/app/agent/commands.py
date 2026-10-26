"""Entende o que o socio respondeu ao agente. Conservador: na duvida, nao age ("unknown")."""

import re
import unicodedata

_CONFIRM = {"1", "confirmar", "confirma", "confirmo", "confirmado", "sim", "sim pode confirmar"}
_CANCEL = {"2", "cancelar", "cancela", "cancelo", "cancelado"}
_HELP = {"ajuda", "menu", "help", "oi", "ola", "bom dia", "boa tarde", "boa noite"}
_STUCK_WORDS = ("parad", "pendenc", "atrasad")
_AGENDA_WORDS = ("agenda", "compromisso")
_AGENDA_PHRASES = ("o que tenho", "tenho hoje", "tenho amanha")


def _plain(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9? ]", " ", stripped)).strip()


def parse_command(text: str) -> str:
    """confirm, cancel, stuck, agenda, help ou unknown.

    Confirmar e cancelar so valem com a palavra (ou o numero) sozinha: uma frase longa que
    cita "confirmar" nao confirma nada.
    """
    plain = _plain(text or "")
    if not plain:
        return "unknown"
    if plain in _CONFIRM:
        return "confirm"
    if plain in _CANCEL:
        return "cancel"
    if plain == "?" or plain in _HELP:
        return "help"
    if any(word in plain for word in _STUCK_WORDS):
        return "stuck"
    if any(word in plain for word in _AGENDA_WORDS) or any(p in plain for p in _AGENDA_PHRASES):
        return "agenda"
    return "unknown"
