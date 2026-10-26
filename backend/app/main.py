import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import psycopg
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout

from app.agent.nl.llm import IntentLLM, build_intent_llm
from app.agent.nl.service import DEFAULT_DAILY_CAP as NL_DAILY_CAP
from app.agent.sender import MessageSender, build_sender
from app.agent.webhook import make_runtime
from app.agent.webhook import router as agent_webhook_router
from app.api.appointments import router as appointments_router
from app.api.auth import router as auth_router
from app.api.channels import router as channels_router
from app.api.demand_writes import router as demand_writes_router
from app.api.demands import router as demands_router
from app.api.deps import AuthSettings
from app.api.people import router as people_router
from app.cases.llm import CaseLLM, build_case_llm
from app.cases.service import DEFAULT_DAILY_CAP
from app.channel_health import EvolutionLike
from app.classification.factory import build_classifier
from app.classification.llm import LLMClassifier
from app.db import DEFAULT_APP_ROLE, Database
from app.evolution_client import EvolutionClient
from app.limits import BodyLimitMiddleware
from app.migrate import apply_migrations
from app.provisioning import create_runtime_role
from app.security.throttle import LoginThrottle
from app.spa import add_security_headers, mount_spa
from app.webhooks import router as webhooks_router
from app.worker import AgentWorker, BackgroundWorker, HealthMonitor

logger = logging.getLogger(__name__)

DEFAULT_MAX_BODY_BYTES = 2_000_000
DEFAULT_TOKEN_TTL_SECONDS = 8 * 3600


def create_app(
    database_url: str | None = None,
    *,
    admin_url: str | None = None,
    auto_migrate: bool = False,
    app_role: str = DEFAULT_APP_ROLE,
    pool_max: int = 5,
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
    runtime_password: str | None = None,
    jwt_secret: str | None = None,
    token_ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
    static_dir: str | Path | None = None,
    worker_interval_seconds: float | None = None,
    classifier: LLMClassifier | None = None,
    evolution: EvolutionLike | None = None,
    health_interval_seconds: float = 60,
    agent_sender: MessageSender | None = None,
    agent_app_url: str = "",
    agent_interval_seconds: float = 60,
    agent_webhook_secret: str | None = None,
    case_llm: CaseLLM | None = None,
    case_daily_cap: int = DEFAULT_DAILY_CAP,
    intent_llm: IntentLLM | None = None,
    nl_daily_cap: int = NL_DAILY_CAP,
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
        workers: list[BackgroundWorker] = []
        if db is not None and worker_interval_seconds:
            workers.append(
                BackgroundWorker(
                    db,
                    classifier,
                    interval_seconds=worker_interval_seconds,
                    case_llm=case_llm,
                    daily_cap=case_daily_cap,
                )
            )
        if db is not None and evolution is not None:
            workers.append(HealthMonitor(db, evolution, interval_seconds=health_interval_seconds))
        if db is not None and agent_sender is not None:
            workers.append(
                AgentWorker(
                    db,
                    agent_sender,
                    app_url=agent_app_url,
                    interval_seconds=agent_interval_seconds,
                )
            )
        for worker in workers:
            worker.start()
        try:
            yield
        finally:
            for worker in workers:
                worker.stop()
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
    app.state.agent = (
        make_runtime(agent_sender, agent_webhook_secret, agent_app_url, intent_llm, nl_daily_cap)
        if agent_sender is not None and agent_webhook_secret
        else None
    )
    app.state.auth = AuthSettings(jwt_secret, token_ttl_seconds, LoginThrottle())
    app.add_middleware(BodyLimitMiddleware, max_bytes=max_body_bytes)
    add_security_headers(app)
    app.include_router(webhooks_router)
    app.include_router(agent_webhook_router)
    app.include_router(auth_router)
    app.include_router(demands_router)
    app.include_router(demand_writes_router)
    app.include_router(people_router)
    app.include_router(channels_router)
    app.include_router(appointments_router)

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

    mount_spa(app, static_dir)  # por ultimo: a SPA so pega o que nenhuma rota do backend pegou
    return app


_admin_url = os.environ.get("DATABASE_URL")
_evolution = (
    EvolutionClient(os.environ["EVOLUTION_URL"], os.environ["EVOLUTION_API_KEY"])
    if os.environ.get("EVOLUTION_URL") and os.environ.get("EVOLUTION_API_KEY")
    else None
)
_agent_sender = build_sender(os.environ, _evolution)
if _agent_sender is not None:
    logger.warning("agente dos socios ligado em modo %s", _agent_sender.mode)
_intent_llm, _intent_note = build_intent_llm(os.environ) if _agent_sender else (None, "")
if _agent_sender is not None:
    logger.warning("%s", _intent_note)
_worker_interval = float(os.environ.get("WORKER_INTERVAL_SECONDS", "0"))
_classifier, _classifier_note = build_classifier(os.environ) if _worker_interval else (None, "")
if _worker_interval:
    logger.warning("worker ligado a cada %ss: %s", _worker_interval, _classifier_note)
_case_llm, _case_note = build_case_llm(os.environ) if _worker_interval else (None, "")
if _worker_interval:
    logger.warning("%s", _case_note)
app = create_app(
    os.environ.get("APP_DATABASE_URL") or _admin_url,
    admin_url=_admin_url,
    auto_migrate=os.environ.get("AUTO_MIGRATE") == "1",
    app_role=os.environ.get("APP_DB_ROLE", DEFAULT_APP_ROLE),
    pool_max=int(os.environ.get("DB_POOL_MAX", "5")),
    max_body_bytes=int(os.environ.get("MAX_BODY_BYTES", str(DEFAULT_MAX_BODY_BYTES))),
    runtime_password=os.environ.get("APP_DB_PASSWORD"),
    static_dir=os.environ.get("STATIC_DIR"),
    jwt_secret=os.environ.get("JWT_SECRET") or None,
    token_ttl_seconds=int(os.environ.get("TOKEN_TTL_MINUTES", "480")) * 60,
    worker_interval_seconds=_worker_interval or None,
    classifier=_classifier,
    evolution=_evolution,
    agent_sender=_agent_sender,
    agent_app_url=os.environ.get("AGENT_APP_URL", ""),
    agent_webhook_secret=os.environ.get("AGENT_WEBHOOK_SECRET") or None,
    case_llm=_case_llm,
    case_daily_cap=int(os.environ.get("CASE_DAILY_CAP", str(DEFAULT_DAILY_CAP))),
    intent_llm=_intent_llm,
    nl_daily_cap=int(os.environ.get("AGENT_NL_DAILY_CAP", str(NL_DAILY_CAP))),
    health_interval_seconds=float(os.environ.get("HEALTH_INTERVAL_SECONDS", "60")),
)
