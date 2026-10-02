from __future__ import annotations

import math
import threading
import time
from collections import defaultdict, deque
from typing import Any


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._counters: dict[str, float] = defaultdict(float)
        self._gauges: dict[str, float] = {}
        self._hist: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=4096))
        self._events: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=20000))
        self.started_at = time.time()

    def inc(self, name: str, amount: float = 1.0) -> None:
        with self._lock:
            self._counters[name] += amount
            self._events[name].append(time.monotonic())

    def gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = float(value)

    def observe(self, name: str, value: float) -> None:
        if not math.isfinite(float(value)):
            return
        with self._lock:
            self._hist[name].append(float(value))

    def rate(self, name: str, window_s: float = 60.0) -> float:
        now = time.monotonic()
        with self._lock:
            q = self._events[name]
            while q and now - q[0] > window_s:
                q.popleft()
            return len(q) / max(window_s, 1e-9)

    @staticmethod
    def _percentile(values: list[float], p: float) -> float | None:
        if not values:
            return None
        values = sorted(values)
        idx = (len(values) - 1) * p
        lo = int(idx)
        hi = min(len(values) - 1, lo + 1)
        frac = idx - lo
        return values[lo] * (1 - frac) + values[hi] * frac

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            hist = {name: list(values) for name, values in self._hist.items()}
            counters = dict(self._counters)
            gauges = dict(self._gauges)
        percentiles = {
            name: {
                "n": len(values),
                "p50": self._percentile(values, 0.50),
                "p95": self._percentile(values, 0.95),
                "p99": self._percentile(values, 0.99),
            }
            for name, values in hist.items()
        }
        return {
            "started_at": self.started_at,
            "uptime_s": round(time.time() - self.started_at, 3),
            "counters": counters,
            "gauges": gauges,
            "rates_per_second_60s": {name: self.rate(name, 60.0) for name in counters},
            "histograms": percentiles,
        }
