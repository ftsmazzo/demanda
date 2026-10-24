import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout

from app.db import DEFAULT_APP_ROLE, Database
from app.limits import BodyLimitMiddleware
from app.migrate import apply_migrations
from app.provisioning import create_runtime_role
from app.webhooks import router as webhooks_router

logger = logging.getLogger(__name__)

DEFAULT_MAX_BODY_BYTES = 2_000_000


def create_app(
    database_url: str | None = None,
    *,
    admin_url: str | None = None,
    auto_migrate: bool = False,
    app_role: str = DEFAULT_APP_ROLE,
    pool_max: int = 5,
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
    runtime_password: str | None = None,
) -> FastAPI:
    """database_url: conexao de runtime. admin_url: dono do schema, so para migrations."""
    db = Database(database_url, app_role=app_role, max_size=pool_max) if database_url else None

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if db is not None:
            if auto_migrate:
                owner_url = admin_url or database_url
                apply_migrations(owner_url)
                if runtime_password:
                    with psycopg.connect(owner_url, autocommit=True) as conn:
                        create_runtime_role(conn, password=runtime_password)
            db.open()
        try:
            yield
        finally:
            if db is not None:
                db.close()

    app = FastAPI(
        title="Demanda",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.db = db
    app.add_middleware(BodyLimitMiddleware, max_bytes=max_body_bytes)
    app.include_router(webhooks_router)

    @app.exception_handler(PoolTimeout)
    async def pool_timeout_handler(_: Request, __: PoolTimeout) -> JSONResponse:
        logger.error("pool de conexoes esgotado")
        return JSONResponse({"detail": "database busy"}, status_code=503)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready() -> dict[str, str]:
        if db is None or not db.ping():
            raise HTTPException(status_code=503, detail="database unavailable")
        return {"status": "ok"}

    return app


_admin_url = os.environ.get("DATABASE_URL")
app = create_app(
    os.environ.get("APP_DATABASE_URL") or _admin_url,
    admin_url=_admin_url,
    auto_migrate=os.environ.get("AUTO_MIGRATE") == "1",
    app_role=os.environ.get("APP_DB_ROLE", DEFAULT_APP_ROLE),
    pool_max=int(os.environ.get("DB_POOL_MAX", "5")),
    max_body_bytes=int(os.environ.get("MAX_BODY_BYTES", str(DEFAULT_MAX_BODY_BYTES))),
    runtime_password=os.environ.get("APP_DB_PASSWORD"),
)
