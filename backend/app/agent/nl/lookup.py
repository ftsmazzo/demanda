"""Acha pessoas, clientes e demandas pelo nome que o socio escreveu (sem acento, sem caixa)."""

import re
import unicodedata
from uuid import UUID

import psycopg

_ACCENTED = "áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ"
_PLAIN = "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC"
_STOP = {"de", "da", "do", "das", "dos", "a", "o", "e", "em", "para", "pra", "no", "na", "com"}


def fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", fold(text)) if len(t) >= 2 and t not in _STOP]


def folded(column: str) -> str:
    """Expressao SQL que tira acentos e caixa de uma coluna de texto."""
    return f"lower(translate({column}, '{_ACCENTED}', '{_PLAIN}'))"


_BS = chr(92)


def _like_patterns(words: list[str]) -> list[str]:
    """Padroes LIKE com %, _ e a propria barra escapados: a busca e literal."""
    escaped = [
        w.replace(_BS, _BS * 2).replace("%", _BS + "%").replace("_", _BS + "_") for w in words
    ]
    return [f"%{w}%" for w in escaped]


def find_users(conn: psycopg.Connection, name: str) -> list[tuple[UUID, str]]:
    """Pessoas ativas cujo nome comeca com cada palavra citada. Nome completo igual vence."""
    wanted = tokens(name)
    if not wanted:
        return []
    rows = conn.execute("SELECT id, name FROM users WHERE active ORDER BY name, id").fetchall()
    exact = [(uid, full) for uid, full in rows if fold(full).split() == fold(name).split()]
    if len(exact) == 1:
        return exact
    found = []
    for uid, full in rows:
        parts = tokens(full)
        if all(any(part.startswith(word) for part in parts) for word in wanted):
            found.append((uid, full))
    return found


def find_contacts(conn: psycopg.Connection, name: str, limit: int = 6) -> list[tuple[UUID, str]]:
    wanted = tokens(name)
    if not wanted:
        return []
    return conn.execute(
        f"SELECT id, COALESCE(name, phone) FROM contacts WHERE name IS NOT NULL "
        f"AND {folded('name')} LIKE ALL(%s) ORDER BY priority DESC, updated_at DESC, id LIMIT %s",
        (_like_patterns(wanted), limit),
    ).fetchall()


def find_demands(
    conn: psycopg.Connection, text: str, *, open_only: bool, limit: int = 4
) -> list[tuple[UUID, str]]:
    wanted = tokens(text)
    if not wanted:
        return []
    haystack = folded("(d.title || ' ' || COALESCE(d.summary, '') || ' ' || COALESCE(c.name, ''))")
    status = "AND d.status <> 'concluido' " if open_only else ""
    return conn.execute(
        "SELECT d.id, d.title FROM demands d LEFT JOIN contacts c ON c.id = d.contact_id "
        f"WHERE {haystack} LIKE ALL(%s) {status}"
        "ORDER BY d.last_activity_at DESC, d.id LIMIT %s",
        (_like_patterns(wanted), limit),
    ).fetchall()
