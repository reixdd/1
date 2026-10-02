from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

try:
    import duckdb
    DUCKDB_AVAILABLE = True
    DUCKDB_IMPORT_ERROR = ""
except Exception as exc:
    duckdb = None
    DUCKDB_AVAILABLE = False
    DUCKDB_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

from .metrics import Metrics
from .research_ledger import ResearchLedger


class ColdArchive:
    """DuckDB research history with batched Parquet export.

    The SQLite outbox remains the durable hand-off point. DuckDB is the queryable
    historical store. Parquet files are exported in coarse batches instead of one
    tiny file per event.
    """

    def __init__(self, history_dir: Path, ledger: ResearchLedger, metrics: Metrics,
                 export_batch_rows: int = 10_000) -> None:
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.history_dir / "research.duckdb"
        self.parquet_dir = self.history_dir / "parquet"
        self.parquet_dir.mkdir(parents=True, exist_ok=True)
        self.ledger = ledger
        self.metrics = metrics
        self.export_batch_rows = max(1000, int(export_batch_rows))
        # Serialize all DuckDB file access in-process. DuckDB rejects mixing
        # read-only and read-write configurations for the same database instance,
        # and status/science/archive tasks can overlap. One async gate keeps every
        # connection short-lived, same-mode, and deterministic.
        self._io_lock = asyncio.Lock()
        self._schema_ready = False
        self._stopping = False
        self.available = DUCKDB_AVAILABLE
        self.import_error = DUCKDB_IMPORT_ERROR
        self._last_exported_seq = 0

    async def open(self) -> None:
        if not self.available:
            self.metrics.gauge("cold_archive_available", 0)
            return
        self.metrics.gauge("cold_archive_available", 1)
        await self._ensure_open()
        await self.refresh_metrics()

    async def _ensure_open(self) -> None:
        """Idempotently create/open the COLD schema before any query.

        API/status tests and isolated runtime components are allowed to call
        ``status`` or ``query`` before the full application lifecycle has called
        ``open``. That must report an empty archive, not fail because the table
        has not been created yet.
        """
        if not self.available or self._schema_ready:
            return
        async with self._io_lock:
            if not self._schema_ready:
                await asyncio.to_thread(self._open_sync)

    def _connect_sync(self):
        # Use one access mode everywhere in this single JARVIS process. Do not
        # mix read_only=True readers with read/write archive connections.
        return duckdb.connect(str(self.db_path), read_only=False)

    def _open_sync(self) -> None:
        con = self._connect_sync()
        try:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS research_events(
                    archive_seq BIGINT,
                    record_kind VARCHAR NOT NULL,
                    record_id VARCHAR NOT NULL,
                    event_time DOUBLE NOT NULL,
                    identity_key VARCHAR,
                    payload_json VARCHAR NOT NULL,
                    ingested_at DOUBLE NOT NULL,
                    UNIQUE(record_kind, record_id)
                )
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS archive_meta(
                    key VARCHAR PRIMARY KEY,
                    value VARCHAR NOT NULL,
                    updated_at DOUBLE NOT NULL
                )
                """
            )
            row = con.execute("SELECT value FROM archive_meta WHERE key='last_exported_seq'").fetchone()
            self._last_exported_seq = int(row[0]) if row else 0
            self._schema_ready = True
        finally:
            con.close()

    async def run(self) -> None:
        if not self.available:
            while not self._stopping:
                await asyncio.sleep(30.0)
            return
        while not self._stopping:
            try:
                await self.flush_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.metrics.inc("cold_archive_errors_total")
            try:
                await asyncio.sleep(5.0)
            except asyncio.CancelledError:
                raise

    def stop(self) -> None:
        self._stopping = True

    async def flush_once(self, limit: int = 2000) -> int:
        if not self.available:
            return 0
        await self._ensure_open()
        rows = await self.ledger.pending_outbox(limit)
        if not rows:
            await self.refresh_metrics()
            return 0
        async with self._io_lock:
            await asyncio.to_thread(self._insert_batch_sync, rows)
            # Export under the same gate so status/science cannot race the write.
            await asyncio.to_thread(self._export_sync, False)
        await self.ledger.mark_outbox_archived([int(row["seq"]) for row in rows])
        self.metrics.inc("cold_archive_flush_total")
        self.metrics.inc("cold_archive_rows_total", len(rows))
        await self.refresh_metrics()
        return len(rows)

    def _insert_batch_sync(self, rows: list[dict[str, Any]]) -> None:
        con = self._connect_sync()
        try:
            ingested = time.time()
            con.executemany(
                """INSERT OR IGNORE INTO research_events
                   (archive_seq,record_kind,record_id,event_time,identity_key,payload_json,ingested_at)
                   VALUES(?,?,?,?,?,?,?)""",
                [
                    (
                        int(row["seq"]), row["record_kind"], row["record_id"], float(row["event_time"]),
                        row.get("identity_key"), row["payload_json"], ingested,
                    )
                    for row in rows
                ],
            )
        finally:
            con.close()

    async def _maybe_export(self, force: bool = False) -> int:
        if not self.available:
            return 0
        await self._ensure_open()
        async with self._io_lock:
            return await asyncio.to_thread(self._export_sync, force)

    def _export_sync(self, force: bool) -> int:
        con = self._connect_sync()
        try:
            row = con.execute(
                "SELECT COUNT(*), COALESCE(MAX(archive_seq),0) FROM research_events WHERE archive_seq > ?",
                [self._last_exported_seq],
            ).fetchone()
            pending, max_seq = int(row[0]), int(row[1])
            if pending <= 0 or (not force and pending < self.export_batch_rows):
                return 0
            stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
            target = self.parquet_dir / f"research-{self._last_exported_seq + 1:012d}-{max_seq:012d}-{stamp}.parquet"
            target_sql = str(target).replace("'", "''")
            con.execute(
                f"""COPY (
                       SELECT * FROM research_events
                       WHERE archive_seq > {int(self._last_exported_seq)} AND archive_seq <= {max_seq}
                       ORDER BY archive_seq
                     ) TO '{target_sql}'
                     (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 122880)"""
            )
            self._last_exported_seq = max_seq
            con.execute(
                """INSERT INTO archive_meta(key,value,updated_at) VALUES('last_exported_seq',?,?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at""",
                [str(max_seq), time.time()],
            )
            self.metrics.inc("cold_parquet_exports_total")
            return pending
        finally:
            con.close()

    async def close(self) -> None:
        self._stopping = True
        if not self.available:
            return
        await self.flush_once()
        await self._maybe_export(force=True)
        await self.refresh_metrics()

    async def refresh_metrics(self) -> None:
        if not self.available:
            return
        await self._ensure_open()
        async with self._io_lock:
            stats = await asyncio.to_thread(self._stats_sync)
        for key, value in stats.items():
            if isinstance(value, (int, float)):
                self.metrics.gauge(f"cold_{key}", value)

    def _stats_sync(self) -> dict[str, Any]:
        con = self._connect_sync()
        try:
            rows = int(con.execute("SELECT COUNT(*) FROM research_events").fetchone()[0])
            kinds = {
                row[0]: int(row[1])
                for row in con.execute("SELECT record_kind, COUNT(*) FROM research_events GROUP BY record_kind").fetchall()
            }
        finally:
            con.close()
        files = list(self.parquet_dir.glob("*.parquet"))
        return {
            "rows": rows,
            "parquet_files": len(files),
            "parquet_bytes": sum(path.stat().st_size for path in files if path.exists()),
            "last_exported_seq": self._last_exported_seq,
            "kinds": kinds,
        }

    async def status(self) -> dict[str, Any]:
        if not self.available:
            return {"available": False, "dependency_error": self.import_error, "rows": 0, "parquet_files": 0}
        await self._ensure_open()
        async with self._io_lock:
            stats = await asyncio.to_thread(self._stats_sync)
        return {"available": True, **stats}

    async def query(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        if not self.available:
            return []
        await self._ensure_open()
        async with self._io_lock:
            return await asyncio.to_thread(self._query_sync, sql, params or [])

    def _query_sync(self, sql: str, params: list[Any]) -> list[dict[str, Any]]:
        con = self._connect_sync()
        try:
            rel = con.execute(sql, params)
            columns = [desc[0] for desc in rel.description]
            return [dict(zip(columns, row)) for row in rel.fetchall()]
        finally:
            con.close()
