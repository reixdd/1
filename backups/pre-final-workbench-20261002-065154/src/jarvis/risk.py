from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Any, Awaitable, Callable

import httpx

from .capabilities import CapabilityRegistry
from .config import Settings
from .evidence import EvidenceStore
from .metrics import Metrics
from .models import Observation, SecurityEvidence

EVM_CHAIN_IDS = {"eth": "1", "bsc": "56", "base": "8453"}


class RiskBrain:
    """Aggregates timestamped security evidence without producing a mystery score."""

    def __init__(
        self,
        settings: Settings,
        store: EvidenceStore,
        metrics: Metrics,
        registry: CapabilityRegistry,
        on_evidence: Callable[[SecurityEvidence], Awaitable[None]] | None = None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.metrics = metrics
        self.registry = registry
        self.on_evidence = on_evidence
        self._targets: deque[tuple[str, str, str]] = deque(maxlen=5000)
        self._seen_targets: set[tuple[str, str, str]] = set()
        self._stop = asyncio.Event()
        self._client = httpx.AsyncClient(timeout=settings.http_timeout_seconds)
        self._last_polled: dict[str, float] = {}

    def track(self, obs: Observation) -> None:
        key = (obs.identity.key, obs.chain, obs.contract)
        if key in self._seen_targets:
            return
        self._seen_targets.add(key)
        self._targets.append(key)

    async def close(self) -> None:
        self._stop.set()
        await self._client.aclose()

    async def run(self) -> None:
        if not self.settings.goplus_enabled:
            while not self._stop.is_set():
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=60.0)
                except TimeoutError:
                    pass
            return
        while not self._stop.is_set():
            started = time.perf_counter()
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.metrics.inc("risk_provider_errors_total")
                self.registry.failure("risk.goplus.token_security", exc)
            self.metrics.observe("risk_cycle_latency_ms", (time.perf_counter() - started) * 1000.0)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.settings.risk_interval_seconds)
            except TimeoutError:
                pass

    async def _poll_once(self) -> None:
        now = time.time()
        candidates: list[tuple[str, str, str]] = []
        for item in list(self._targets):
            identity_key, chain, _ = item
            if chain not in EVM_CHAIN_IDS:
                continue
            if now - self._last_polled.get(identity_key, 0.0) < self.settings.risk_refresh_seconds:
                continue
            candidates.append(item)
            if len(candidates) >= self.settings.risk_max_targets_per_cycle:
                break
        for identity_key, chain, contract in candidates:
            await self._fetch_goplus(identity_key, chain, contract)
            self._last_polled[identity_key] = time.time()

    async def _fetch_goplus(self, identity_key: str, chain: str, contract: str) -> None:
        url = f"{self.settings.goplus_base_url.rstrip('/')}/api/v1/token_security/{EVM_CHAIN_IDS[chain]}"
        headers = {}
        if self.settings.goplus_token:
            headers["Authorization"] = f"Bearer {self.settings.goplus_token}"
        started = time.perf_counter()
        response = await self._client.get(url, params={"contract_addresses": contract}, headers=headers)
        latency_ms = (time.perf_counter() - started) * 1000.0
        response.raise_for_status()
        body = response.json()
        result = body.get("result") if isinstance(body, dict) else None
        token_data: dict[str, Any] = {}
        if isinstance(result, dict):
            token_data = result.get(contract.lower()) or result.get(contract) or {}
        if not isinstance(token_data, dict):
            token_data = {}
        inserted = 0
        for field, value in token_data.items():
            if isinstance(value, (dict, list)):
                # Preserve nested provider evidence as-is rather than flattening into a score.
                classification = "CLAIM"
            elif value in (None, "", "unknown", "Unknown"):
                classification = "UNKNOWN"
            else:
                classification = "CLAIM"
            item = SecurityEvidence(
                identity_key=identity_key,
                provider="GoPlus",
                field=str(field),
                value=value,
                classification=classification,
                confidence="PROVIDER_REPORTED",
                source_url=url,
                provenance={"chain_id": EVM_CHAIN_IDS[chain], "read_only": True},
            )
            if await self.store.insert_security(item):
                inserted += 1
                if self.on_evidence:
                    await self.on_evidence(item)
        self.metrics.inc("risk_provider_calls_total")
        self.metrics.inc("risk_evidence_inserted_total", inserted)
        self.metrics.observe("risk_provider_latency_ms", latency_ms)
        self.registry.success("risk.goplus.token_security", latency_ms)

    async def ingest(self, item: SecurityEvidence) -> bool:
        inserted = await self.store.insert_security(item)
        if inserted and self.on_evidence:
            await self.on_evidence(item)
        return inserted

    async def summary(self, identity_key: str) -> dict[str, Any]:
        rows = await self.store.security_for(identity_key, 500)
        by_field: dict[str, list[SecurityEvidence]] = {}
        for row in rows:
            by_field.setdefault(row.field, []).append(row)
        conflicts: list[dict[str, Any]] = []
        unknowns: list[str] = []
        for field, items in by_field.items():
            values = {repr(item.value) for item in items if item.classification != "UNKNOWN"}
            if len(values) > 1:
                conflicts.append({"field": field, "providers": sorted({item.provider for item in items}), "values": sorted(values)})
            if all(item.classification == "UNKNOWN" for item in items):
                unknowns.append(field)
        return {
            "identity_key": identity_key,
            "evidence_count": len(rows),
            "providers": sorted({row.provider for row in rows}),
            "conflicts": conflicts,
            "unknown_fields": sorted(unknowns),
            "evidence": [row.model_dump(mode="json") for row in rows[:100]],
            "safe_score": None,
            "note": "JARVIS preserves provider claims, conflicts and unknowns; it does not synthesize a mystery safety score.",
        }

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.settings.goplus_enabled,
            "provider": "GoPlus" if self.settings.goplus_enabled else None,
            "tracked_targets": len(self._targets),
            "polling_is_optional": True,
            "safe_score": None,
        }
