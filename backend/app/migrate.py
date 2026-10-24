"""Runner minimo de migrations SQL versionadas (app/migrations/NNNN_nome.sql)."""

import logging
from contextlib import suppress
from pathlib import Path

import psycopg

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
ADVISORY_LOCK_KEY = 727274  # evita corrida entre replicas subindo juntas


def apply_migrations(database_url: str) -> list[str]:
    """Aplica as migrations pendentes e devolve as versoes aplicadas agora."""
    applied_now: list[str] = []
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (ADVISORY_LOCK_KEY,))
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
            )
            done = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
            for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
                if path.stem in done:
                    continue
                with conn.transaction():
                    conn.execute(path.read_text(encoding="utf-8"))
                    conn.execute(
                        "INSERT INTO schema_migrations (version) VALUES (%s)", (path.stem,)
                    )
                applied_now.append(path.stem)
                logger.info("migration aplicada: %s", path.stem)
        finally:
            # o lock e de sessao: se a conexao caiu ele ja foi liberado
            with suppress(psycopg.Error):
                conn.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_KEY,))
    return applied_now
