"""Limite de tentativas de login por (tenant, e-mail), em memoria."""

import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable


class LoginThrottle:
    """Bloqueia uma chave depois de `max_failures` falhas dentro de `window_seconds`.

    Em memoria e por processo (o servico roda com uma replica). O numero de chaves e limitado
    para que tentativas com e-mails inventados nao consumam memoria sem fim.
    """

    def __init__(
        self,
        *,
        max_failures: int = 5,
        window_seconds: int = 600,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = 10_000,
    ) -> None:
        self._max_failures = max_failures
        self._window = window_seconds
        self._clock = clock
        self._max_keys = max_keys
        self._failures: OrderedDict[Hashable, list[float]] = OrderedDict()
        self._lock = threading.Lock()

    def _recent(self, key: Hashable) -> list[float]:
        cutoff = self._clock() - self._window
        recent = [stamp for stamp in self._failures.get(key, []) if stamp > cutoff]
        if recent:
            self._failures[key] = recent
        else:
            self._failures.pop(key, None)
        return recent

    def is_blocked(self, key: Hashable) -> bool:
        with self._lock:
            return len(self._recent(key)) >= self._max_failures

    def record_failure(self, key: Hashable) -> None:
        with self._lock:
            recent = self._recent(key)
            recent.append(self._clock())
            self._failures[key] = recent
            self._failures.move_to_end(key)
            while len(self._failures) > self._max_keys:
                self._failures.popitem(last=False)

    def reset(self, key: Hashable) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def size(self) -> int:
        return len(self._failures)
