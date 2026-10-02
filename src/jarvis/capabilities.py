from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Capability:
    capability_id: str
    brain: str
    provider: str
    chains: tuple[str, ...] = ()
    read_only: bool = True
    freshness: str = "live"
    cost: str = "local"
    latency_ms: float | None = None
    rate_budget: str | None = None
    cooldown_until: float | None = None
    health: str = "READY"
    required_inputs: tuple[str, ...] = ()
    last_success_at: float | None = None
    last_failure_at: float | None = None
    last_error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class CapabilityRegistry:
    """Single registry of research capabilities visible to JARVIS and specialists."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._items: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        if not capability.read_only:
            raise ValueError("clean JARVIS capability registry accepts read-only research capabilities only")
        with self._lock:
            self._items[capability.capability_id] = capability

    def success(self, capability_id: str, latency_ms: float | None = None) -> None:
        with self._lock:
            item = self._items.get(capability_id)
            if not item:
                return
            item.health = "READY"
            item.last_success_at = time.time()
            item.last_error = None
            if latency_ms is not None:
                item.latency_ms = float(latency_ms)

    def failure(self, capability_id: str, error: Exception | str, cooldown_until: float | None = None) -> None:
        with self._lock:
            item = self._items.get(capability_id)
            if not item:
                return
            item.health = "DEGRADED"
            item.last_failure_at = time.time()
            item.last_error = str(error)[:300]
            item.cooldown_until = cooldown_until

    def get(self, capability_id: str) -> Capability | None:
        with self._lock:
            return self._items.get(capability_id)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            rows = [asdict(item) for item in self._items.values()]
        rows.sort(key=lambda row: (row["brain"], row["capability_id"]))
        return {
            "count": len(rows),
            "read_only_only": all(row["read_only"] for row in rows),
            "items": rows,
        }
