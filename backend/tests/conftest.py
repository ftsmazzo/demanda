import os
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.migrate import apply_migrations
from app.provisioning import create_channel, create_tenant


@dataclass(frozen=True)
class ChannelFixture:
    tenant_id: UUID
    channel_id: UUID
    secret: str

    @property
    def path(self) -> str:
        return f"/webhooks/evolution/{self.channel_id}"

    @property
    def headers(self) -> dict[str, str]:
        return {"X-Webhook-Secret": self.secret}


@pytest.fixture(scope="session")
def admin_url() -> Iterator[str]:
    """Postgres de teste: TEST_DATABASE_URL (CI) ou um Postgres embutido (local)."""
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        apply_migrations(url)
        yield url
        return
    import pgserver

    server = pgserver.get_server(tempfile.mkdtemp(prefix="demanda-pg-"))
    try:
        url = server.get_uri()
        apply_migrations(url)
        yield url
    finally:
        server.cleanup()


@pytest.fixture
def admin_conn(admin_url: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(admin_url, autocommit=True) as conn:
        yield conn


@pytest.fixture
def app_conn(admin_url: str) -> Iterator[psycopg.Connection]:
    """Conexao com o papel restrito da aplicacao (RLS vale para ele)."""
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute("SET ROLE demanda_app")
        yield conn


def _new_slug() -> str:
    return f"t-{uuid4().hex[:10]}"


@pytest.fixture
def tenant_id(admin_conn: psycopg.Connection) -> UUID:
    slug = _new_slug()
    return create_tenant(admin_conn, slug=slug, name=f"Tenant {slug}")


@pytest.fixture
def channel(admin_conn: psycopg.Connection, tenant_id: UUID) -> ChannelFixture:
    channel_id, secret = create_channel(
        admin_conn, tenant_id=tenant_id, name="Principal", instance_name="escritorio"
    )
    return ChannelFixture(tenant_id, channel_id, secret)


@pytest.fixture
def other_channel(admin_conn: psycopg.Connection) -> ChannelFixture:
    """Canal de OUTRO tenant, para testes de isolamento."""
    slug = _new_slug()
    other_tenant = create_tenant(admin_conn, slug=slug, name=f"Tenant {slug}")
    channel_id, secret = create_channel(
        admin_conn, tenant_id=other_tenant, name="Outro", instance_name="outro"
    )
    return ChannelFixture(other_tenant, channel_id, secret)


@pytest.fixture
def client(admin_url: str) -> Iterator[TestClient]:
    with TestClient(create_app(database_url=admin_url)) as test_client:
        yield test_client


@pytest.fixture
def database(admin_url: str):
    from app.db import Database

    db = Database(admin_url)
    db.open()
    try:
        yield db
    finally:
        db.close()
