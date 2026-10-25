"""Processamento em segundo plano: classifica as mensagens novas e abre/atualiza as demandas."""

import logging
import threading
from collections import Counter
from collections.abc import Callable

from app.channel_health import EvolutionLike, check_channels
from app.classification.llm import LLMClassifier
from app.classification.store import classify_pending
from app.core.demands import materialize_demands
from app.db import Database

logger = logging.getLogger(__name__)

CYCLE_LIMIT = 100


def run_cycle(db: Database, llm: LLMClassifier | None, *, limit: int = CYCLE_LIMIT) -> Counter[str]:
    """Uma passada por todos os tenants. Falha de um tenant nao impede os demais."""
    total: Counter[str] = Counter()
    for tenant_id in db.tenant_ids():
        try:
            total.update(classify_pending(db, tenant_id, llm=llm, limit=limit))
            total.update(materialize_demands(db, tenant_id, limit=limit))
        except Exception:
            total["tenant_errors"] += 1
            logger.exception("falha ao processar o tenant %s", tenant_id)
    return total


class BackgroundWorker(threading.Thread):
    def __init__(
        self,
        db: Database,
        llm: LLMClassifier | None,
        *,
        interval_seconds: float,
        on_cycle: Callable[[Counter[str]], None] | None = None,
    ) -> None:
        super().__init__(name="demanda-worker", daemon=True)
        self._db = db
        self._llm = llm
        self._interval = interval_seconds
        self._on_cycle = on_cycle
        self._stop_event = threading.Event()

    def cycle(self) -> Counter[str]:
        return run_cycle(self._db, self._llm)

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                summary = self.cycle()
                if any(summary.get(k) for k in ("classified", "created", "attached")):
                    logger.info("ciclo do worker: %s", dict(summary))
                if self._on_cycle:
                    self._on_cycle(summary)
            except Exception:
                logger.exception("ciclo do worker falhou")
            self._stop_event.wait(self._interval)

    def stop(self) -> None:
        self._stop_event.set()
        self.join(timeout=30)


class HealthMonitor(BackgroundWorker):
    """Confere a Evolution a cada ciclo e busca as mensagens que o webhook nao entregou."""

    def __init__(
        self,
        db: Database,
        evolution: EvolutionLike,
        *,
        interval_seconds: float,
        on_cycle: Callable[[Counter[str]], None] | None = None,
    ) -> None:
        super().__init__(db, None, interval_seconds=interval_seconds, on_cycle=on_cycle)
        self.name = "demanda-health"
        self._evolution = evolution

    def cycle(self) -> Counter[str]:
        return check_channels(self._db, self._evolution)
