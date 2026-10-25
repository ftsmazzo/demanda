"""Contatos: cada telefone que fala com o escritorio vira um contato do tenant."""

from uuid import UUID

import psycopg

_UPSERT = """
    INSERT INTO contacts (tenant_id, phone, name)
    VALUES (%s, %s, %s)
    ON CONFLICT (tenant_id, phone) DO UPDATE SET
        name = COALESCE(contacts.name, EXCLUDED.name),
        updated_at = CASE
            WHEN contacts.name IS NULL AND EXCLUDED.name IS NOT NULL THEN now()
            ELSE contacts.updated_at
        END
    RETURNING id
"""


def upsert_contact(
    conn: psycopg.Connection, *, tenant_id: UUID, phone: str, push_name: str | None, incoming: bool
) -> UUID:
    """Garante o contato e devolve o id.

    So mensagens recebidas podem dar nome (o nome das enviadas e o nosso). Um nome ja existente,
    inclusive o editado por uma pessoa, nunca e sobrescrito.
    """
    name = push_name if incoming and push_name else None
    return conn.execute(_UPSERT, (tenant_id, phone, name)).fetchone()[0]
