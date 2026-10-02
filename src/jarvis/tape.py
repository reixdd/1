from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .metrics import Metrics
from .models import Observation, QuantSnapshot


class MarketTape:
    """Bounded operational SQLite tape.

    SQLite is hot operational state only. Step 2 will introduce Parquet/DuckDB for
    historical research. No VACUUM is run automatically; WAL checkpointing is safe
    and explicit.
    """

    def __init__(self, path: Path, metrics: Metrics, retention_hours: float = 72.0) -> None:
        self.path = Path(path)
        self.metrics = metrics
        self.retention_hours = retention_hours
        self._db: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        self._async_lock = asyncio.Lock()
        self._writes_since_checkpoint = 0
        self._last_maintenance = 0.0

    async def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._open_sync)
        await self._refresh_metrics()

    def _open_sync(self) -> None:
        with self._lock:
            self._db = sqlite3.connect(self.path, timeout=15, check_same_thread=False)
            self._db.row_factory = sqlite3.Row
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA synchronous=NORMAL")
            self._db.execute("PRAGMA foreign_keys=ON")
            self._db.execute("PRAGMA busy_timeout=10000")
            self._db.executescript(
                """
                CREATE TABLE IF NOT EXISTS observations(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    observed_at REAL NOT NULL,
                    received_at REAL NOT NULL,
                    provider TEXT NOT NULL,
                    capability TEXT NOT NULL,
                    chain TEXT NOT NULL,
                    contract TEXT NOT NULL,
                    pool TEXT,
                    identity_key TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    launch_at REAL,
                    price REAL,
                    market_cap REAL,
                    liquidity REAL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS observations_time_idx ON observations(received_at DESC);
                CREATE INDEX IF NOT EXISTS observations_identity_idx ON observations(identity_key, received_at DESC);
                CREATE INDEX IF NOT EXISTS observations_launch_idx ON observations(launch_at DESC);

                CREATE TABLE IF NOT EXISTS quant_snapshots(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_id TEXT NOT NULL UNIQUE,
                    event_id TEXT NOT NULL,
                    identity_key TEXT NOT NULL,
                    evaluated_at REAL NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS quant_time_idx ON quant_snapshots(evaluated_at DESC);
                CREATE INDEX IF NOT EXISTS quant_identity_idx ON quant_snapshots(identity_key, evaluated_at DESC);

                CREATE TABLE IF NOT EXISTS runtime_meta(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );
                """
            )
            self._db.commit()

    async def close(self) -> None:
        async with self._async_lock:
            await asyncio.to_thread(self._close_sync)

    def _close_sync(self) -> None:
        with self._lock:
            if self._db is not None:
                try:
                    self._db.execute("PRAGMA wal_checkpoint(PASSIVE)")
                    self._db.commit()
                finally:
                    self._db.close()
                    self._db = None

    async def append(self, observation: Observation) -> bool:
        async with self._async_lock:
            started = time.perf_counter()
            inserted = await asyncio.to_thread(self._append_sync, observation)
            self.metrics.observe("tape_write_latency_ms", (time.perf_counter() - started) * 1000.0)
            if inserted:
                self.metrics.inc("tape_write_total")
            await self._maybe_maintain_locked()
        await self._refresh_metrics()
        return inserted

    def _append_sync(self, obs: Observation) -> bool:
        assert self._db is not None
        with self._lock:
            payload = obs.model_dump(mode="json")
            before = self._db.total_changes
            self._db.execute(
                """INSERT OR IGNORE INTO observations(
                    event_id, observed_at, received_at, provider, capability, chain, contract, pool,
                    identity_key, event_type, launch_at, price, market_cap, liquidity, payload_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    obs.event_id, obs.observed_at, obs.received_at, obs.provider, obs.capability,
                    obs.chain, obs.contract, obs.pool, obs.identity.key, obs.event_type, obs.launch_at,
                    obs.price, obs.market_cap, obs.liquidity,
                    json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
                ),
            )
            self._db.commit()
            inserted = self._db.total_changes > before
            if inserted:
                self._writes_since_checkpoint += 1
            return inserted

    async def append_quant(self, snap: QuantSnapshot) -> bool:
        async with self._async_lock:
            inserted = await asyncio.to_thread(self._append_quant_sync, snap)
            if inserted:
                self.metrics.inc("quant_persist_total")
            await self._maybe_maintain_locked()
        return inserted

    def _append_quant_sync(self, snap: QuantSnapshot) -> bool:
        assert self._db is not None
        with self._lock:
            before = self._db.total_changes
            self._db.execute(
                "INSERT OR IGNORE INTO quant_snapshots(snapshot_id,event_id,identity_key,evaluated_at,payload_json) VALUES(?,?,?,?,?)",
                (snap.snapshot_id, snap.event_id, snap.identity_key, snap.evaluated_at,
                 json.dumps(snap.model_dump(mode="json"), separators=(",", ":"))),
            )
            self._db.commit()
            inserted = self._db.total_changes > before
            if inserted:
                self._writes_since_checkpoint += 1
            return inserted

    async def _maybe_maintain_locked(self) -> None:
        now = time.time()
        if self._writes_since_checkpoint >= 1000 or now - self._last_maintenance >= 300:
            await asyncio.to_thread(self._maintenance_sync, now)
            self._writes_since_checkpoint = 0
            self._last_maintenance = now

    def _maintenance_sync(self, now: float) -> None:
        assert self._db is not None
        cutoff = now - self.retention_hours * 3600.0
        with self._lock:
            self._db.execute("DELETE FROM observations WHERE received_at < ?", (cutoff,))
            self._db.execute("DELETE FROM quant_snapshots WHERE evaluated_at < ?", (cutoff,))
            self._db.commit()
            self._db.execute("PRAGMA wal_checkpoint(PASSIVE)")

    async def _refresh_metrics(self) -> None:
        stats = await self.stats()
        self.metrics.gauge("tape_rows", stats["observations"])
        self.metrics.gauge("quant_rows", stats["quant_snapshots"])

    async def stats(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._stats_sync)

    def _stats_sync(self) -> dict[str, Any]:
        assert self._db is not None
        with self._lock:
            observations = self._db.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
            quant = self._db.execute("SELECT COUNT(*) FROM quant_snapshots").fetchone()[0]
            latest = self._db.execute("SELECT MAX(received_at) FROM observations").fetchone()[0]
        try:
            size = self.path.stat().st_size
        except OSError:
            size = 0
        return {"path": str(self.path), "observations": observations, "quant_snapshots": quant,
                "latest_received_at": latest, "file_bytes": size, "retention_hours": self.retention_hours}

    async def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._recent_sync, max(1, min(1000, int(limit))))

    def _recent_sync(self, limit: int) -> list[dict[str, Any]]:
        assert self._db is not None
        with self._lock:
            rows = self._db.execute("SELECT payload_json FROM observations ORDER BY seq DESC LIMIT ?", (limit,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    async def history(self, identity_key: str, limit: int = 500) -> list[dict[str, Any]]:
        """Recent observations for one canonical identity, newest first."""
        return await asyncio.to_thread(self._history_sync, str(identity_key), max(1, min(5000, int(limit))))

    def _history_sync(self, identity_key: str, limit: int) -> list[dict[str, Any]]:
        assert self._db is not None
        with self._lock:
            rows = self._db.execute(
                "SELECT payload_json FROM observations WHERE identity_key=? ORDER BY seq DESC LIMIT ?",
                (identity_key, limit),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    async def recent_quant(self, limit: int = 100) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._recent_quant_sync, max(1, min(1000, int(limit))))

    def _recent_quant_sync(self, limit: int) -> list[dict[str, Any]]:
        assert self._db is not None
        with self._lock:
            rows = self._db.execute("SELECT payload_json FROM quant_snapshots ORDER BY seq DESC LIMIT ?", (limit,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    async def restore_recent(self, since_seconds: float = 3600.0, limit: int = 10000) -> list[Observation]:
        cutoff = time.time() - max(1.0, since_seconds)
        payloads = await asyncio.to_thread(self._restore_sync, cutoff, limit)
        out = []
        for payload in payloads:
            try:
                out.append(Observation.model_validate(payload))
            except Exception:
                continue
        return out

    def _restore_sync(self, cutoff: float, limit: int) -> list[dict[str, Any]]:
        assert self._db is not None
        with self._lock:
            rows = self._db.execute(
                "SELECT payload_json FROM observations WHERE received_at >= ? ORDER BY seq ASC LIMIT ?",
                (cutoff, max(1, min(100000, int(limit)))),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]
