"""Usuario autenticado: sempre lido do banco, para refletir mudancas de papel e desativacao."""

from dataclasses import dataclass
from uuid import UUID

import psycopg


@dataclass(frozen=True, slots=True)
class CurrentUser:
    id: UUID
    tenant_id: UUID
    email: str
    name: str
    role: str
    sectors: tuple[str, ...]


def load_user(conn: psycopg.Connection, tenant_id: UUID, user_id: UUID) -> CurrentUser | None:
    """Le o usuario ativo (a conexao ja esta presa ao tenant pelo RLS)."""
    row = conn.execute(
        "SELECT id, tenant_id, email, name, role FROM users "
        "WHERE id = %s AND tenant_id = %s AND active",
        (user_id, tenant_id),
    ).fetchone()
    if row is None:
        return None
    sectors = conn.execute(
        "SELECT sector FROM user_sectors WHERE user_id = %s ORDER BY sector", (user_id,)
    ).fetchall()
    return CurrentUser(*row, tuple(sector[0] for sector in sectors))
