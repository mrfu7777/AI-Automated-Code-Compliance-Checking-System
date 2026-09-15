from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable
from time import monotonic
from typing import TypeVar

T = TypeVar("T")


class ExternalModelUnavailable(RuntimeError):
    pass


class ExternalModelRateLimited(RuntimeError):
    pass


class ModelCallGuard:
    """Bound optional model calls without coupling them to deterministic review execution."""

    def __init__(
        self,
        *,
        enabled: bool,
        timeout_seconds: float,
        requests_per_minute: int,
        failure_threshold: int = 3,
        recovery_seconds: float = 60,
    ) -> None:
        self.enabled = enabled
        self.timeout_seconds = timeout_seconds
        self.requests_per_minute = requests_per_minute
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self._requests: deque[float] = deque()
        self._consecutive_failures = 0
        self._circuit_opened_at: float | None = None

    async def run(self, call: Callable[[], Awaitable[T]]) -> T:
        if not self.enabled:
            raise ExternalModelUnavailable("External model integration is disabled")
        now = monotonic()
        if self._circuit_opened_at is not None:
            if now - self._circuit_opened_at < self.recovery_seconds:
                raise ExternalModelUnavailable("External model circuit breaker is open")
            self._circuit_opened_at = None
            self._consecutive_failures = 0
        while self._requests and now - self._requests[0] >= 60:
            self._requests.popleft()
        if len(self._requests) >= self.requests_per_minute:
            raise ExternalModelRateLimited("External model request limit reached")
        self._requests.append(now)
        try:
            result = await asyncio.wait_for(call(), timeout=self.timeout_seconds)
        except Exception:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.failure_threshold:
                self._circuit_opened_at = monotonic()
            raise
        self._consecutive_failures = 0
        return result
