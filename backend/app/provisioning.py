"""Criacao de tenants e canais (uso administrativo: CLI e testes)."""

import hashlib
import secrets
from uuid import UUID

import psycopg
from psycopg import sql


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def create_tenant(conn: psycopg.Connection, *, slug: str, name: str) -> UUID:
    row = conn.execute(
        "INSERT INTO tenants (slug, name) VALUES (%s, %s) RETURNING id", (slug, name)
    ).fetchone()
    return row[0]


def create_channel(
    conn: psycopg.Connection,
    *,
    tenant_id: UUID,
    name: str,
    instance_name: str,
    listen_groups: bool = False,
) -> tuple[UUID, str]:
    """Cria o canal e devolve (id, segredo). O segredo so existe aqui; o banco guarda o hash."""
    secret = secrets.token_urlsafe(32)
    row = conn.execute(
        "INSERT INTO channels (tenant_id, name, instance_name, webhook_secret_hash, listen_groups) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (tenant_id, name, instance_name, hash_secret(secret), listen_groups),
    ).fetchone()
    return row[0], secret


def create_runtime_role(
    conn: psycopg.Connection, *, password: str, name: str = "demanda_runtime"
) -> None:
    """Cria (ou atualiza a senha de) o login de runtime, sem privilegios proprios.

    Ele so consegue virar demanda_app (SET ROLE). Mesmo que algum SQL execute RESET ROLE,
    volta a um papel sem acesso a nada.
    """
    exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (name,)).fetchone()
    verb = "ALTER" if exists else "CREATE"
    conn.execute(
        sql.SQL("{} ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT PASSWORD {}").format(
            sql.SQL(verb), sql.Identifier(name), sql.Literal(password)
        )
    )
    conn.execute(sql.SQL("GRANT demanda_app TO {}").format(sql.Identifier(name)))
