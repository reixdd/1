from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("duckdb")

from jarvis.history import ColdArchive
from jarvis.metrics import Metrics
from jarvis.models import ExperimentRecord
from jarvis.research_ledger import ResearchLedger


@pytest.mark.asyncio
async def test_cold_archive_consumes_sqlite_outbox_and_exports_parquet(tmp_path: Path):
    metrics = Metrics()
    ledger = ResearchLedger(tmp_path / "op.sqlite3", metrics)
    await ledger.open()
    archive = ColdArchive(tmp_path / "history", ledger, metrics, export_batch_rows=1000)
    await archive.open()
    try:
        exp = ExperimentRecord(
            hypothesis_id="TEST", identity_key="base:a:b", source_event_id="e",
            entry_price=1.0, entry_liquidity=1000,
        )
        assert await ledger.insert_experiment(exp)
        assert await archive.flush_once() >= 1
        assert (await archive.status())["rows"] >= 1
        await archive._maybe_export(force=True)
        assert (await archive.status())["parquet_files"] >= 1
    finally:
        await archive.close()
        await ledger.close()


@pytest.mark.asyncio
async def test_cold_archive_status_before_open_is_empty_and_concurrent_access_is_safe(tmp_path: Path):
    """Regression for Windows Step-2 install: status/query may race startup.

    The archive must create its schema lazily and every in-process connection must
    use the same DuckDB access mode.
    """
    metrics = Metrics()
    ledger = ResearchLedger(tmp_path / "op.sqlite3", metrics)
    await ledger.open()
    archive = ColdArchive(tmp_path / "history", ledger, metrics, export_batch_rows=1000)
    try:
        # No explicit archive.open() on purpose.
        status, rows = await __import__("asyncio").gather(
            archive.status(),
            archive.query("SELECT COUNT(*) AS n FROM research_events"),
        )
        assert status["rows"] == 0
        assert rows == [{"n": 0}]

        # Repeat concurrently after schema creation to catch access-mode races.
        status2, rows2 = await __import__("asyncio").gather(
            archive.status(),
            archive.query("SELECT COUNT(*) AS n FROM research_events"),
        )
        assert status2["rows"] == 0
        assert rows2 == [{"n": 0}]
    finally:
        await archive.close()
        await ledger.close()
