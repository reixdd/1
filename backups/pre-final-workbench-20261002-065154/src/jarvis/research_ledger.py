from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .metrics import Metrics
from .models import ExperimentRecord, ForwardMark, OnlinePrediction


class ResearchLedger:
    """Operational research state stored in the same bounded SQLite file.

    Domain ownership stays outside this repository: ExperimentEngine owns experiment
    semantics and OnlineLearner owns model semantics. This class only persists their
    operational state and an archive outbox.
    """

    def __init__(self, path: Path, metrics: Metrics) -> None:
        self.path = Path(path)
        self.metrics = metrics
        self._db: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        self._async_lock = asyncio.Lock()

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
                CREATE TABLE IF NOT EXISTS hypothesis_state(
                    hypothesis_id TEXT NOT NULL,
                    identity_key TEXT NOT NULL,
                    active INTEGER NOT NULL,
                    updated_at REAL NOT NULL,
                    source_event_id TEXT,
                    PRIMARY KEY(hypothesis_id, identity_key)
                );

                CREATE TABLE IF NOT EXISTS experiments(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    experiment_id TEXT NOT NULL UNIQUE,
                    hypothesis_id TEXT NOT NULL,
                    identity_key TEXT NOT NULL,
                    source_event_id TEXT NOT NULL,
                    opened_at REAL NOT NULL,
                    entry_price REAL,
                    status TEXT NOT NULL,
                    control INTEGER NOT NULL DEFAULT 0,
                    max_return_pct REAL,
                    min_return_pct REAL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS experiments_identity_idx
                    ON experiments(identity_key, opened_at DESC);
                CREATE INDEX IF NOT EXISTS experiments_status_idx
                    ON experiments(status, opened_at);

                CREATE TABLE IF NOT EXISTS forward_marks(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    mark_id TEXT NOT NULL UNIQUE,
                    experiment_id TEXT NOT NULL,
                    identity_key TEXT NOT NULL,
                    horizon_seconds INTEGER NOT NULL,
                    due_at REAL NOT NULL,
                    observed_at REAL NOT NULL,
                    complete INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    UNIQUE(experiment_id, horizon_seconds)
                );
                CREATE INDEX IF NOT EXISTS forward_marks_experiment_idx
                    ON forward_marks(experiment_id, horizon_seconds);

                CREATE TABLE IF NOT EXISTS online_predictions(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    prediction_id TEXT NOT NULL UNIQUE,
                    experiment_id TEXT NOT NULL UNIQUE,
                    identity_key TEXT NOT NULL,
                    model_key TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    label_due_at REAL NOT NULL,
                    label INTEGER,
                    label_observed_at REAL,
                    learned_at REAL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS online_predictions_due_idx
                    ON online_predictions(label_due_at, learned_at);

                CREATE TABLE IF NOT EXISTS cold_outbox(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_kind TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    event_time REAL NOT NULL,
                    identity_key TEXT,
                    payload_json TEXT NOT NULL,
                    archived_at REAL,
                    UNIQUE(record_kind, record_id)
                );
                CREATE INDEX IF NOT EXISTS cold_outbox_pending_idx
                    ON cold_outbox(archived_at, seq);
                """
            )
            self._db.commit()

    async def close(self) -> None:
        async with self._async_lock:
            await asyncio.to_thread(self._close_sync)

    def _close_sync(self) -> None:
        with self._lock:
            if self._db is not None:
                self._db.execute("PRAGMA wal_checkpoint(PASSIVE)")
                self._db.commit()
                self._db.close()
                self._db = None

    async def get_condition(self, hypothesis_id: str, identity_key: str) -> bool:
        return await asyncio.to_thread(self._get_condition_sync, hypothesis_id, identity_key)

    def _get_condition_sync(self, hypothesis_id: str, identity_key: str) -> bool:
        assert self._db is not None
        with self._lock:
            row = self._db.execute(
                "SELECT active FROM hypothesis_state WHERE hypothesis_id=? AND identity_key=?",
                (hypothesis_id, identity_key),
            ).fetchone()
        return bool(row[0]) if row else False

    async def set_condition(self, hypothesis_id: str, identity_key: str, active: bool,
                            source_event_id: str, updated_at: float | None = None) -> None:
        await asyncio.to_thread(
            self._set_condition_sync, hypothesis_id, identity_key, active,
            source_event_id, updated_at or time.time(),
        )

    def _set_condition_sync(self, hypothesis_id: str, identity_key: str, active: bool,
                            source_event_id: str, updated_at: float) -> None:
        assert self._db is not None
        with self._lock:
            self._db.execute(
                """INSERT INTO hypothesis_state(hypothesis_id, identity_key, active, updated_at, source_event_id)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(hypothesis_id, identity_key) DO UPDATE SET
                     active=excluded.active, updated_at=excluded.updated_at, source_event_id=excluded.source_event_id""",
                (hypothesis_id, identity_key, int(active), updated_at, source_event_id),
            )
            self._db.commit()

    async def insert_experiment(self, record: ExperimentRecord) -> bool:
        inserted = await asyncio.to_thread(self._insert_experiment_sync, record)
        if inserted:
            self.metrics.inc("experiments_created_total")
        await self._refresh_metrics()
        return inserted

    def _insert_experiment_sync(self, record: ExperimentRecord) -> bool:
        assert self._db is not None
        payload = json.dumps(record.model_dump(mode="json"), separators=(",", ":"))
        with self._lock:
            before = self._db.total_changes
            self._db.execute(
                """INSERT OR IGNORE INTO experiments(
                     experiment_id,hypothesis_id,identity_key,source_event_id,opened_at,entry_price,status,
                     control,max_return_pct,min_return_pct,payload_json
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    record.experiment_id, record.hypothesis_id, record.identity_key, record.source_event_id,
                    record.opened_at, record.entry_price, record.status, int(record.control),
                    record.max_return_pct, record.min_return_pct, payload,
                ),
            )
            inserted = self._db.total_changes > before
            if inserted:
                self._enqueue_sync("experiment", record.experiment_id, record.opened_at, record.identity_key, payload)
            self._db.commit()
        return inserted

    async def get_experiment(self, experiment_id: str) -> ExperimentRecord | None:
        return await asyncio.to_thread(self._get_experiment_sync, experiment_id)

    def _get_experiment_sync(self, experiment_id: str) -> ExperimentRecord | None:
        assert self._db is not None
        with self._lock:
            row = self._db.execute(
                "SELECT payload_json FROM experiments WHERE experiment_id=?", (experiment_id,)
            ).fetchone()
        return ExperimentRecord.model_validate(json.loads(row[0])) if row else None

    async def open_experiments(self, identity_key: str | None = None) -> list[ExperimentRecord]:
        return await asyncio.to_thread(self._open_experiments_sync, identity_key)

    def _open_experiments_sync(self, identity_key: str | None) -> list[ExperimentRecord]:
        assert self._db is not None
        query = "SELECT payload_json FROM experiments WHERE status='OPEN'"
        params: tuple[Any, ...] = ()
        if identity_key:
            query += " AND identity_key=?"
            params = (identity_key,)
        query += " ORDER BY opened_at ASC"
        with self._lock:
            rows = self._db.execute(query, params).fetchall()
        return [ExperimentRecord.model_validate(json.loads(row[0])) for row in rows]

    async def update_excursion(self, experiment_id: str, return_pct: float) -> ExperimentRecord | None:
        result = await asyncio.to_thread(self._update_excursion_sync, experiment_id, return_pct)
        return result

    def _update_excursion_sync(self, experiment_id: str, return_pct: float) -> ExperimentRecord | None:
        assert self._db is not None
        with self._lock:
            row = self._db.execute(
                "SELECT payload_json FROM experiments WHERE experiment_id=?", (experiment_id,)
            ).fetchone()
            if not row:
                return None
            record = ExperimentRecord.model_validate(json.loads(row[0]))
            record.max_return_pct = return_pct if record.max_return_pct is None else max(record.max_return_pct, return_pct)
            record.min_return_pct = return_pct if record.min_return_pct is None else min(record.min_return_pct, return_pct)
            payload = json.dumps(record.model_dump(mode="json"), separators=(",", ":"))
            self._db.execute(
                "UPDATE experiments SET max_return_pct=?, min_return_pct=?, payload_json=? WHERE experiment_id=?",
                (record.max_return_pct, record.min_return_pct, payload, experiment_id),
            )
            self._db.commit()
            return record

    async def insert_mark(self, mark: ForwardMark) -> bool:
        inserted = await asyncio.to_thread(self._insert_mark_sync, mark)
        if inserted:
            self.metrics.inc("forward_marks_total")
            if mark.complete:
                self.metrics.inc("forward_marks_complete_total")
        await self._refresh_metrics()
        return inserted

    def _insert_mark_sync(self, mark: ForwardMark) -> bool:
        assert self._db is not None
        payload = json.dumps(mark.model_dump(mode="json"), separators=(",", ":"))
        with self._lock:
            before = self._db.total_changes
            self._db.execute(
                """INSERT OR IGNORE INTO forward_marks(
                     mark_id,experiment_id,identity_key,horizon_seconds,due_at,observed_at,complete,payload_json
                   ) VALUES(?,?,?,?,?,?,?,?)""",
                (mark.mark_id, mark.experiment_id, mark.identity_key, mark.horizon_seconds,
                 mark.due_at, mark.observed_at, int(mark.complete), payload),
            )
            inserted = self._db.total_changes > before
            if inserted:
                self._enqueue_sync("forward_mark", mark.mark_id, mark.observed_at, mark.identity_key, payload)
                if mark.horizon_seconds >= 86400:
                    row = self._db.execute(
                        "SELECT payload_json FROM experiments WHERE experiment_id=?", (mark.experiment_id,)
                    ).fetchone()
                    if row:
                        rec = ExperimentRecord.model_validate(json.loads(row[0]))
                        rec.status = "MATURED"
                        updated = json.dumps(rec.model_dump(mode="json"), separators=(",", ":"))
                        self._db.execute(
                            "UPDATE experiments SET status='MATURED', payload_json=? WHERE experiment_id=?",
                            (updated, mark.experiment_id),
                        )
            self._db.commit()
        return inserted

    async def marks_for(self, experiment_id: str) -> list[ForwardMark]:
        return await asyncio.to_thread(self._marks_for_sync, experiment_id)

    def _marks_for_sync(self, experiment_id: str) -> list[ForwardMark]:
        assert self._db is not None
        with self._lock:
            rows = self._db.execute(
                "SELECT payload_json FROM forward_marks WHERE experiment_id=? ORDER BY horizon_seconds",
                (experiment_id,),
            ).fetchall()
        return [ForwardMark.model_validate(json.loads(row[0])) for row in rows]

    async def insert_prediction(self, prediction: OnlinePrediction) -> bool:
        inserted = await asyncio.to_thread(self._insert_prediction_sync, prediction)
        if inserted:
            self.metrics.inc("online_predictions_total")
        await self._refresh_metrics()
        return inserted

    def _insert_prediction_sync(self, prediction: OnlinePrediction) -> bool:
        assert self._db is not None
        payload = json.dumps(prediction.model_dump(mode="json"), separators=(",", ":"))
        with self._lock:
            before = self._db.total_changes
            self._db.execute(
                """INSERT OR IGNORE INTO online_predictions(
                     prediction_id,experiment_id,identity_key,model_key,created_at,label_due_at,label,
                     label_observed_at,learned_at,payload_json
                   ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    prediction.prediction_id, prediction.experiment_id, prediction.identity_key,
                    prediction.model_key, prediction.created_at, prediction.label_due_at,
                    None if prediction.label is None else int(prediction.label),
                    prediction.label_observed_at, prediction.learned_at, payload,
                ),
            )
            inserted = self._db.total_changes > before
            if inserted:
                self._enqueue_sync("online_prediction", prediction.prediction_id,
                                   prediction.created_at, prediction.identity_key, payload)
            self._db.commit()
        return inserted

    async def prediction_for_experiment(self, experiment_id: str) -> OnlinePrediction | None:
        return await asyncio.to_thread(self._prediction_for_experiment_sync, experiment_id)

    def _prediction_for_experiment_sync(self, experiment_id: str) -> OnlinePrediction | None:
        assert self._db is not None
        with self._lock:
            row = self._db.execute(
                "SELECT payload_json FROM online_predictions WHERE experiment_id=?", (experiment_id,)
            ).fetchone()
        return OnlinePrediction.model_validate(json.loads(row[0])) if row else None

    async def update_prediction(self, prediction: OnlinePrediction) -> None:
        await asyncio.to_thread(self._update_prediction_sync, prediction)
        await self._refresh_metrics()

    def _update_prediction_sync(self, prediction: OnlinePrediction) -> None:
        assert self._db is not None
        payload = json.dumps(prediction.model_dump(mode="json"), separators=(",", ":"))
        with self._lock:
            self._db.execute(
                """UPDATE online_predictions SET label=?,label_observed_at=?,learned_at=?,payload_json=?
                   WHERE prediction_id=?""",
                (
                    None if prediction.label is None else int(prediction.label),
                    prediction.label_observed_at, prediction.learned_at, payload, prediction.prediction_id,
                ),
            )
            self._enqueue_sync("online_prediction_update", prediction.prediction_id,
                               prediction.label_observed_at or time.time(), prediction.identity_key, payload)
            self._db.commit()

    async def learned_predictions(self) -> list[OnlinePrediction]:
        return await asyncio.to_thread(self._learned_predictions_sync)

    def _learned_predictions_sync(self) -> list[OnlinePrediction]:
        assert self._db is not None
        with self._lock:
            rows = self._db.execute(
                "SELECT payload_json FROM online_predictions WHERE learned_at IS NOT NULL ORDER BY learned_at ASC"
            ).fetchall()
        return [OnlinePrediction.model_validate(json.loads(row[0])) for row in rows]

    async def pending_outbox(self, limit: int = 2000) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._pending_outbox_sync, limit)

    def _pending_outbox_sync(self, limit: int) -> list[dict[str, Any]]:
        assert self._db is not None
        with self._lock:
            rows = self._db.execute(
                """SELECT seq,record_kind,record_id,event_time,identity_key,payload_json
                   FROM cold_outbox WHERE archived_at IS NULL ORDER BY seq ASC LIMIT ?""",
                (max(1, min(10000, int(limit))),),
            ).fetchall()
        return [dict(row) for row in rows]

    async def mark_outbox_archived(self, seqs: list[int], archived_at: float | None = None) -> None:
        if not seqs:
            return
        await asyncio.to_thread(self._mark_outbox_archived_sync, seqs, archived_at or time.time())
        await self._refresh_metrics()

    def _mark_outbox_archived_sync(self, seqs: list[int], archived_at: float) -> None:
        assert self._db is not None
        marks = ",".join("?" for _ in seqs)
        with self._lock:
            self._db.execute(
                f"UPDATE cold_outbox SET archived_at=? WHERE seq IN ({marks})",
                (archived_at, *seqs),
            )
            self._db.commit()

    def _enqueue_sync(self, kind: str, record_id: str, event_time: float,
                      identity_key: str | None, payload: str) -> None:
        assert self._db is not None
        self._db.execute(
            """INSERT OR IGNORE INTO cold_outbox(record_kind,record_id,event_time,identity_key,payload_json)
               VALUES(?,?,?,?,?)""",
            (kind, record_id, event_time, identity_key, payload),
        )

    async def stats(self) -> dict[str, int]:
        return await asyncio.to_thread(self._stats_sync)

    def _stats_sync(self) -> dict[str, int]:
        assert self._db is not None
        with self._lock:
            experiments = self._db.execute("SELECT COUNT(*) FROM experiments").fetchone()[0]
            open_experiments = self._db.execute("SELECT COUNT(*) FROM experiments WHERE status='OPEN'").fetchone()[0]
            marks = self._db.execute("SELECT COUNT(*) FROM forward_marks").fetchone()[0]
            complete_marks = self._db.execute("SELECT COUNT(*) FROM forward_marks WHERE complete=1").fetchone()[0]
            predictions = self._db.execute("SELECT COUNT(*) FROM online_predictions").fetchone()[0]
            labeled = self._db.execute("SELECT COUNT(*) FROM online_predictions WHERE label IS NOT NULL").fetchone()[0]
            learned = self._db.execute("SELECT COUNT(*) FROM online_predictions WHERE learned_at IS NOT NULL").fetchone()[0]
            pending_archive = self._db.execute("SELECT COUNT(*) FROM cold_outbox WHERE archived_at IS NULL").fetchone()[0]
        return {
            "experiments": experiments,
            "open_experiments": open_experiments,
            "forward_marks": marks,
            "complete_marks": complete_marks,
            "predictions": predictions,
            "labeled": labeled,
            "learned": learned,
            "pending_archive": pending_archive,
        }

    async def recent_experiments(self, limit: int = 100) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._recent_experiments_sync, limit)

    def _recent_experiments_sync(self, limit: int) -> list[dict[str, Any]]:
        assert self._db is not None
        with self._lock:
            rows = self._db.execute(
                "SELECT payload_json FROM experiments ORDER BY seq DESC LIMIT ?",
                (max(1, min(1000, int(limit))),),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]


    async def outcomes_after(self, identity_key: str, observed_at: float, horizon_seconds: int = 900) -> list[dict[str, Any]]:
        return await asyncio.to_thread(self._outcomes_after_sync, identity_key, observed_at, horizon_seconds)

    def _outcomes_after_sync(self, identity_key: str, observed_at: float, horizon_seconds: int) -> list[dict[str, Any]]:
        assert self._db is not None
        with self._lock:
            rows = self._db.execute(
                """SELECT e.opened_at,m.payload_json
                   FROM experiments e JOIN forward_marks m ON m.experiment_id=e.experiment_id
                   WHERE e.identity_key=? AND e.opened_at>=? AND m.horizon_seconds=? AND m.complete=1
                   ORDER BY e.opened_at ASC LIMIT 25""",
                (identity_key, float(observed_at), int(horizon_seconds)),
            ).fetchall()
        out=[]
        for row in rows:
            payload=json.loads(row["payload_json"])
            payload["experiment_opened_at"]=float(row["opened_at"])
            out.append(payload)
        return out

    async def label_base_rate(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._label_base_rate_sync)

    def _label_base_rate_sync(self) -> dict[str, Any]:
        assert self._db is not None
        with self._lock:
            row = self._db.execute(
                "SELECT COUNT(*), SUM(CASE WHEN label=1 THEN 1 ELSE 0 END) FROM online_predictions WHERE label IS NOT NULL"
            ).fetchone()
        n=int(row[0] or 0)
        positive=int(row[1] or 0)
        return {"n": n, "positive": positive, "rate": (positive/n if n else None)}

    async def _refresh_metrics(self) -> None:
        stats = await self.stats()
        for key, value in stats.items():
            self.metrics.gauge(f"research_{key}", value)
