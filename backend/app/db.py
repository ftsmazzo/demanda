import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import psycopg
from psycopg import sql
from psycopg_pool import ConnectionPool, PoolTimeout

logger = logging.getLogger(__name__)

DEFAULT_APP_ROLE = "demanda_app"
POOL_TIMEOUT_SECONDS = 5


@dataclass(frozen=True, slots=True)
class ChannelAuth:
    tenant_id: UUID
    webhook_secret_hash: str
    listen_groups: bool


@dataclass(frozen=True, slots=True)
class AuthUser:
    user_id: UUID
    tenant_id: UUID
    password_hash: str
    role: str
    name: str


class Database:
    """Pool de conexoes que sempre opera com o papel restrito (RLS vale para ele).

    Padrao: toda leitura/escrita de dados de negocio passa por tenant_transaction.
    Fora dela o tenant e nulo e o RLS devolve zero linhas.
    """

    def __init__(self, url: str, *, app_role: str = DEFAULT_APP_ROLE, max_size: int = 5) -> None:
        self._app_role = app_role
        self._pool = ConnectionPool(
            url,
            min_size=1,
            max_size=max_size,
            timeout=POOL_TIMEOUT_SECONDS,
            kwargs={"autocommit": True},
            configure=self._configure,
            check=ConnectionPool.check_connection,
            open=False,
        )

    def _configure(self, conn: psycopg.Connection) -> None:
        conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(self._app_role)))

    def open(self) -> None:
        self._pool.open(wait=True, timeout=15)

    def close(self) -> None:
        self._pool.close()

    def tenant_ids(self) -> list[UUID]:
        """Ids de todos os tenants, pela funcao SECURITY DEFINER (o runtime nao le a tabela)."""
        with self._pool.connection() as conn:
            return [row[0] for row in conn.execute("SELECT list_tenant_ids()").fetchall()]

    def list_channels(self) -> list[tuple[Any, ...]]:
        """(id, tenant_id, instance_name, listen_groups, health_state, last_reconciled_at)."""
        with self._pool.connection() as conn:
            return conn.execute("SELECT * FROM list_channels()").fetchall()

    def ping(self) -> bool:
        try:
            with self._pool.connection() as conn:
                conn.execute("SELECT 1")
        except (psycopg.Error, PoolTimeout):
            logger.warning("ping do banco falhou")
            return False
        return True

    def auth_channel(self, channel_id: UUID) -> ChannelAuth | None:
        with self._pool.connection() as conn:
            row = conn.execute("SELECT * FROM auth_channel(%s)", (channel_id,)).fetchone()
        return ChannelAuth(*row) if row else None

    def auth_user(self, tenant_slug: str, email: str) -> AuthUser | None:
        with self._pool.connection() as conn:
            row = conn.execute("SELECT * FROM auth_user(%s, %s)", (tenant_slug, email)).fetchone()
        return AuthUser(*row) if row else None

    @contextmanager
    def tenant_transaction(self, tenant_id: UUID) -> Iterator[psycopg.Connection]:
        """Transacao com o tenant fixado; o RLS limita tudo a ele."""
        with self._pool.connection() as conn, conn.transaction():
            conn.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),))
            yield conn
