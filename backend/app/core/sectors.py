"""Setores do tenant: o nome vira o identificador e so setores ativos recebem trabalho novo."""

import copy
import re
import unicodedata
from typing import Any

import psycopg

MAX_SLUG = 40
PALETTE = ("#b0563a", "#4c7f5f", "#5a6fb0", "#a8508a", "#8a7a2c", "#3f8f9a", "#7d5a3c", "#6b6f78")


def slugify(label: str) -> str:
    """'Jurídico Trabalhista' -> 'juridico-trabalhista'; vazio se nada aproveitavel."""
    plain = unicodedata.normalize("NFD", label.lower())
    plain = "".join(ch for ch in plain if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")[:MAX_SLUG].strip("-")


SectorInfo = tuple[str, str]  # (slug, nome)
MAX_PROMPT_LABEL = 40


def active_infos(conn: psycopg.Connection) -> tuple[SectorInfo, ...]:
    """Setores ativos do tenant da conexao, triagem primeiro (e o destino quando nada serve)."""
    rows = conn.execute(
        "SELECT slug, label FROM sectors WHERE active ORDER BY slug <> 'triagem', created_at, slug"
    ).fetchall()
    return tuple((row[0], row[1]) for row in rows)


def labels(conn: psycopg.Connection) -> dict[str, str]:
    """slug -> nome de todos os setores (inclusive os desligados, que ainda tem trabalho antigo)."""
    return dict(conn.execute("SELECT slug, label FROM sectors").fetchall())


def allowed_slugs(infos: tuple[SectorInfo, ...]) -> tuple[str, ...] | None:
    """Conjunto aceito na resposta da IA; None quando o contexto nao trouxe a lista do tenant."""
    return tuple(slug for slug, _ in infos) if infos else None


def schema_with_sectors(
    schema: dict[str, Any], infos: tuple[SectorInfo, ...], *, extra: tuple[str, ...] = ()
) -> dict[str, Any]:
    """Copia do esquema de saida com o enum de setor trocado pelos setores ativos do tenant."""
    if not infos:
        return schema
    changed = copy.deepcopy(schema)
    changed["properties"]["sector"]["enum"] = [*(slug for slug, _ in infos), *extra]
    return changed


def _prompt_text(text: str) -> str:
    return " ".join(text.replace("<", " ").replace(">", " ").split())[:MAX_PROMPT_LABEL]


def prompt_block(infos: tuple[SectorInfo, ...]) -> str:
    """Frase para o prompt de sistema com os setores validos deste escritorio (nome saneado)."""
    if not infos:
        return ""
    listed = ", ".join(f"{slug} ({_prompt_text(label)})" for slug, label in infos)
    return (
        "Setores ativos neste escritorio (use SOMENTE estes identificadores; os que nao tem "
        f"descricao acima sao proprios do escritorio, escolha pelo nome): {listed}."
    )


def is_active(conn: psycopg.Connection, slug: str) -> bool:
    return (
        conn.execute("SELECT 1 FROM sectors WHERE slug = %s AND active", (slug,)).fetchone()
        is not None
    )
