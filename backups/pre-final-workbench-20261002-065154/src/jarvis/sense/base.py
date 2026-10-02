from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from ..metrics import Metrics
from ..models import Observation

Emit = Callable[[Observation], Awaitable[None]]


@dataclass(slots=True)
class ProviderHealth:
    lane: str
    provider: str
    state: str = "STARTING"
    cycles: int = 0
    calls: int = 0
    observations: int = 0
    errors: int = 0
    last_started_at: float | None = None
    last_success_at: float | None = None
    last_error_at: float | None = None
    last_error: str = ""
    latency_ms: float | None = None
    call_times: deque[float] = field(default_factory=lambda: deque(maxlen=4096))
    budget_max_calls: int = 60
    budget_window_s: float = 60.0

    def budget(self) -> dict:
        now = time.monotonic()
        while self.call_times and now - self.call_times[0] > self.budget_window_s:
            self.call_times.popleft()
        used = len(self.call_times)
        return {
            "used": used,
            "remaining": max(0, self.budget_max_calls - used),
            "max_calls": self.budget_max_calls,
            "window_s": self.budget_window_s,
            "utilization": used / max(1, self.budget_max_calls),
        }

    def snapshot(self) -> dict:
        return {
            "lane": self.lane,
            "provider": self.provider,
            "state": self.state,
            "cycles": self.cycles,
            "calls": self.calls,
            "observations": self.observations,
            "errors": self.errors,
            "last_started_at": self.last_started_at,
            "last_success_at": self.last_success_at,
            "last_error_at": self.last_error_at,
            "last_error": self.last_error,
            "latency_ms": self.latency_ms,
            "budget": self.budget(),
        }


class ProviderLane:
    """Independent supervised polling lane.

    One lane failing never raises through another lane. This is intentionally not an
    asyncio.TaskGroup: first-failure sibling cancellation is the wrong semantic for
    independent market-data providers.
    """

    def __init__(self, lane: str, provider: str, interval_s: float,
                 poll: Callable[[], Awaitable[tuple[list[Observation], int]]], emit: Emit,
                 metrics: Metrics, *, budget_max_calls: int = 60, budget_window_s: float = 60.0,
                 initial_delay_s: float = 0.0) -> None:
        self.interval_s = interval_s
        self.poll = poll
        self.emit = emit
        self.metrics = metrics
        self.initial_delay_s = initial_delay_s
        self.health = ProviderHealth(lane=lane, provider=provider,
                                     budget_max_calls=budget_max_calls, budget_window_s=budget_window_s)
        self._stop = asyncio.Event()

    async def run(self) -> None:
        if self.initial_delay_s:
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.initial_delay_s)
                return
            except TimeoutError:
                pass
        while not self._stop.is_set():
            started = time.perf_counter()
            self.health.last_started_at = time.time()
            self.health.state = "LIVE" if self.health.last_success_at else "STARTING"
            try:
                observations, calls = await self.poll()
                self.health.cycles += 1
                self.health.calls += int(calls)
                self.health.observations += len(observations)
                for _ in range(max(0, int(calls))):
                    self.health.call_times.append(time.monotonic())
                for obs in observations:
                    await self.emit(obs)
                    self.metrics.inc("provider_observations_total")
                self.health.last_success_at = time.time()
                self.health.last_error = ""
                self.health.state = "LIVE"
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.health.errors += 1
                self.health.last_error_at = time.time()
                self.health.last_error = f"{type(exc).__name__}: {str(exc)[:240]}"
                self.health.state = "DEGRADED"
                self.metrics.inc("provider_errors_total")
            finally:
                latency = (time.perf_counter() - started) * 1000.0
                self.health.latency_ms = latency
                self.metrics.observe(f"provider_latency_ms:{self.health.lane}", latency)
            delay = max(0.25, self.interval_s - (time.perf_counter() - started))
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=delay)
            except TimeoutError:
                pass

    def stop(self) -> None:
        self._stop.set()
