from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .metrics import Metrics
from .models import AgentRunRecord, AttentionPacket, GraphEdgeRecord, MemoryItem, SecurityEvidence, SocialMention


class EvidenceStore:
    """Operational Stage-3 evidence storage.

    This store owns evidence persistence only. Risk/Graph/Social/Memory/Attention
    retain semantic ownership of their data.
    """

    def __init__(self, path: Path, metrics: Metrics) -> None:
        self.path = Path(path)
        self.metrics = metrics
        self._db: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        self._async_lock = asyncio.Lock()
        self._fts_available = False

    async def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._open_sync)

    def _open_sync(self) -> None:
        with self._lock:
            self._db = sqlite3.connect(self.path, timeout=15, check_same_thread=False)
            self._db.row_factory = sqlite3.Row
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA synchronous=NORMAL")
            self._db.execute("PRAGMA busy_timeout=10000")
            self._db.executescript(
                """
                CREATE TABLE IF NOT EXISTS security_evidence(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    evidence_id TEXT NOT NULL UNIQUE,
                    identity_key TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    observed_at REAL NOT NULL,
                    field TEXT NOT NULL,
                    value_json TEXT,
                    classification TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    source_url TEXT,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS security_identity_idx ON security_evidence(identity_key, observed_at DESC);

                CREATE TABLE IF NOT EXISTS graph_edges(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    edge_id TEXT NOT NULL UNIQUE,
                    source_node TEXT NOT NULL,
                    target_node TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    first_seen_at REAL NOT NULL,
                    last_seen_at REAL NOT NULL,
                    observations INTEGER NOT NULL,
                    weight REAL NOT NULL,
                    identity_key TEXT,
                    evidence_id TEXT,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS graph_identity_idx ON graph_edges(identity_key, last_seen_at DESC);
                CREATE INDEX IF NOT EXISTS graph_source_idx ON graph_edges(source_node, last_seen_at DESC);
                CREATE INDEX IF NOT EXISTS graph_target_idx ON graph_edges(target_node, last_seen_at DESC);

                CREATE TABLE IF NOT EXISTS social_mentions(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    mention_id TEXT NOT NULL UNIQUE,
                    identity_key TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    observed_at REAL NOT NULL,
                    independent INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS social_identity_idx ON social_mentions(identity_key, observed_at DESC);
                CREATE INDEX IF NOT EXISTS social_source_idx ON social_mentions(source_id, observed_at DESC);

                CREATE TABLE IF NOT EXISTS memory_items(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_id TEXT NOT NULL UNIQUE,
                    identity_key TEXT,
                    classification TEXT NOT NULL,
                    observed_at REAL NOT NULL,
                    source TEXT NOT NULL,
                    content TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS memory_identity_idx ON memory_items(identity_key, observed_at DESC);

                CREATE TABLE IF NOT EXISTS attention_packets(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    packet_id TEXT NOT NULL UNIQUE,
                    identity_key TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS attention_identity_idx ON attention_packets(identity_key, created_at DESC);

                CREATE TABLE IF NOT EXISTS agent_runs(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL UNIQUE,
                    packet_id TEXT NOT NULL,
                    identity_key TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    started_at REAL NOT NULL,
                    finished_at REAL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS agent_packet_idx ON agent_runs(packet_id, started_at DESC);
                """
            )
            try:
                self._db.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(memory_id UNINDEXED, content, source, classification)"
                )
                self._fts_available = True
            except sqlite3.OperationalError:
                self._fts_available = False
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

    async def insert_security(self, item: SecurityEvidence) -> bool:
        inserted = await asyncio.to_thread(self._insert_security_sync, item)
        if inserted:
            self.metrics.inc("security_evidence_total")
        return inserted

    def _insert_security_sync(self, item: SecurityEvidence) -> bool:
        assert self._db is not None
        payload = json.dumps(item.model_dump(mode="json"), separators=(",", ":"))
        with self._lock:
            before = self._db.total_changes
            self._db.execute(
                """INSERT OR IGNORE INTO security_evidence(
                    evidence_id,identity_key,provider,observed_at,field,value_json,classification,confidence,source_url,payload_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (item.evidence_id, item.identity_key, item.provider, item.observed_at, item.field,
                 json.dumps(item.value, separators=(",", ":")), item.classification, item.confidence,
                 item.source_url, payload),
            )
            self._db.commit()
            return self._db.total_changes > before

    async def security_for(self, identity_key: str, limit: int = 200) -> list[SecurityEvidence]:
        return await asyncio.to_thread(self._security_for_sync, identity_key, limit)

    def _security_for_sync(self, identity_key: str, limit: int) -> list[SecurityEvidence]:
        assert self._db is not None
        with self._lock:
            rows = self._db.execute(
                "SELECT payload_json FROM security_evidence WHERE identity_key=? ORDER BY observed_at DESC LIMIT ?",
                (identity_key, max(1, min(2000, int(limit)))),
            ).fetchall()
        return [SecurityEvidence.model_validate(json.loads(row[0])) for row in rows]

    async def upsert_edge(self, item: GraphEdgeRecord) -> None:
        await asyncio.to_thread(self._upsert_edge_sync, item)
        self.metrics.inc("graph_edge_observations_total")

    def _upsert_edge_sync(self, item: GraphEdgeRecord) -> None:
        assert self._db is not None
        with self._lock:
            existing = self._db.execute(
                "SELECT observations,first_seen_at FROM graph_edges WHERE edge_id=?", (item.edge_id,)
            ).fetchone()
            if existing:
                item.observations = int(existing["observations"]) + 1
                item.first_seen_at = float(existing["first_seen_at"])
            payload = json.dumps(item.model_dump(mode="json"), separators=(",", ":"))
            self._db.execute(
                """INSERT INTO graph_edges(edge_id,source_node,target_node,relation,provider,first_seen_at,last_seen_at,
                    observations,weight,identity_key,evidence_id,payload_json)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(edge_id) DO UPDATE SET
                      last_seen_at=excluded.last_seen_at, observations=excluded.observations,
                      weight=excluded.weight, identity_key=excluded.identity_key,
                      evidence_id=COALESCE(excluded.evidence_id,graph_edges.evidence_id), payload_json=excluded.payload_json""",
                (item.edge_id, item.source_node, item.target_node, item.relation, item.provider,
                 item.first_seen_at, item.last_seen_at, item.observations, item.weight,
                 item.identity_key, item.evidence_id, payload),
            )
            self._db.commit()

    async def edges(self, identity_key: str | None = None, limit: int = 5000) -> list[GraphEdgeRecord]:
        return await asyncio.to_thread(self._edges_sync, identity_key, limit)

    def _edges_sync(self, identity_key: str | None, limit: int) -> list[GraphEdgeRecord]:
        assert self._db is not None
        if identity_key:
            query = "SELECT payload_json FROM graph_edges WHERE identity_key=? ORDER BY last_seen_at DESC LIMIT ?"
            params = (identity_key, max(1, min(20000, int(limit))))
        else:
            query = "SELECT payload_json FROM graph_edges ORDER BY last_seen_at DESC LIMIT ?"
            params = (max(1, min(20000, int(limit))),)
        with self._lock:
            rows = self._db.execute(query, params).fetchall()
        return [GraphEdgeRecord.model_validate(json.loads(row[0])) for row in rows]

    async def insert_social(self, item: SocialMention) -> bool:
        inserted = await asyncio.to_thread(self._insert_social_sync, item)
        if inserted:
            self.metrics.inc("social_mentions_total")
            if item.independent:
                self.metrics.inc("social_independent_mentions_total")
        return inserted

    def _insert_social_sync(self, item: SocialMention) -> bool:
        assert self._db is not None
        payload = json.dumps(item.model_dump(mode="json"), separators=(",", ":"))
        with self._lock:
            before = self._db.total_changes
            self._db.execute(
                """INSERT OR IGNORE INTO social_mentions(
                    mention_id,identity_key,source_id,source_type,observed_at,independent,payload_json
                ) VALUES(?,?,?,?,?,?,?)""",
                (item.mention_id, item.identity_key, item.source_id, item.source_type,
                 item.observed_at, int(item.independent), payload),
            )
            self._db.commit()
            return self._db.total_changes > before

    async def social_for(self, identity_key: str, limit: int = 200) -> list[SocialMention]:
        return await asyncio.to_thread(self._social_for_sync, identity_key, limit)

    def _social_for_sync(self, identity_key: str, limit: int) -> list[SocialMention]:
        assert self._db is not None
        with self._lock:
            rows = self._db.execute(
                "SELECT payload_json FROM social_mentions WHERE identity_key=? ORDER BY observed_at DESC LIMIT ?",
                (identity_key, max(1, min(2000, int(limit)))),
            ).fetchall()
        return [SocialMention.model_validate(json.loads(row[0])) for row in rows]

    async def social_by_source(self, source_id: str, limit: int = 500) -> list[SocialMention]:
        return await asyncio.to_thread(self._social_by_source_sync, source_id, limit)

    def _social_by_source_sync(self, source_id: str, limit: int) -> list[SocialMention]:
        assert self._db is not None
        with self._lock:
            rows = self._db.execute(
                "SELECT payload_json FROM social_mentions WHERE source_id=? ORDER BY observed_at DESC LIMIT ?",
                (source_id, max(1, min(5000, int(limit)))),
            ).fetchall()
        return [SocialMention.model_validate(json.loads(row[0])) for row in rows]

    async def insert_memory(self, item: MemoryItem) -> bool:
        inserted = await asyncio.to_thread(self._insert_memory_sync, item)
        if inserted:
            self.metrics.inc("memory_items_total")
        return inserted

    def _insert_memory_sync(self, item: MemoryItem) -> bool:
        assert self._db is not None
        payload = json.dumps(item.model_dump(mode="json"), separators=(",", ":"))
        with self._lock:
            before = self._db.total_changes
            self._db.execute(
                """INSERT OR IGNORE INTO memory_items(memory_id,identity_key,classification,observed_at,source,content,payload_json)
                   VALUES(?,?,?,?,?,?,?)""",
                (item.memory_id, item.identity_key, item.classification, item.observed_at,
                 item.source, item.content, payload),
            )
            inserted = self._db.total_changes > before
            if inserted and self._fts_available:
                self._db.execute(
                    "INSERT OR REPLACE INTO memory_fts(rowid,memory_id,content,source,classification) "
                    "VALUES((SELECT seq FROM memory_items WHERE memory_id=?),?,?,?,?)",
                    (item.memory_id, item.memory_id, item.content, item.source, item.classification),
                )
            self._db.commit()
            return inserted

    async def search_memory(self, query: str, limit: int = 50) -> list[MemoryItem]:
        return await asyncio.to_thread(self._search_memory_sync, query, limit)

    def _search_memory_sync(self, query: str, limit: int) -> list[MemoryItem]:
        assert self._db is not None
        q = str(query or "").strip()
        if not q:
            return []
        with self._lock:
            rows = []
            if self._fts_available:
                try:
                    rows = self._db.execute(
                        """SELECT m.payload_json FROM memory_fts f
                           JOIN memory_items m ON m.memory_id=f.memory_id
                           WHERE memory_fts MATCH ? ORDER BY rank LIMIT ?""",
                        (q, max(1, min(500, int(limit)))),
                    ).fetchall()
                except sqlite3.OperationalError:
                    rows = []
            if not rows:
                rows = self._db.execute(
                    "SELECT payload_json FROM memory_items WHERE content LIKE ? ORDER BY observed_at DESC LIMIT ?",
                    (f"%{q}%", max(1, min(500, int(limit)))),
                ).fetchall()
        return [MemoryItem.model_validate(json.loads(row[0])) for row in rows]

    async def insert_attention(self, item: AttentionPacket) -> bool:
        inserted = await asyncio.to_thread(self._insert_attention_sync, item)
        if inserted:
            self.metrics.inc("attention_packets_total")
        return inserted

    def _insert_attention_sync(self, item: AttentionPacket) -> bool:
        assert self._db is not None
        payload = json.dumps(item.model_dump(mode="json"), separators=(",", ":"))
        with self._lock:
            before = self._db.total_changes
            self._db.execute(
                "INSERT OR IGNORE INTO attention_packets(packet_id,identity_key,created_at,status,payload_json) VALUES(?,?,?,?,?)",
                (item.packet_id, item.identity_key, item.created_at, item.status, payload),
            )
            self._db.commit()
            return self._db.total_changes > before

    async def recent_attention(self, limit: int = 100) -> list[AttentionPacket]:
        return await asyncio.to_thread(self._recent_attention_sync, limit)

    def _recent_attention_sync(self, limit: int) -> list[AttentionPacket]:
        assert self._db is not None
        with self._lock:
            rows = self._db.execute(
                "SELECT payload_json FROM attention_packets ORDER BY created_at DESC LIMIT ?",
                (max(1, min(1000, int(limit))),),
            ).fetchall()
        return [AttentionPacket.model_validate(json.loads(row[0])) for row in rows]

    async def insert_agent_run(self, item: AgentRunRecord) -> bool:
        inserted = await asyncio.to_thread(self._insert_agent_run_sync, item)
        if inserted:
            self.metrics.inc("agent_runs_total")
        return inserted

    def _insert_agent_run_sync(self, item: AgentRunRecord) -> bool:
        assert self._db is not None
        payload = json.dumps(item.model_dump(mode="json"), separators=(",", ":"))
        with self._lock:
            before = self._db.total_changes
            self._db.execute(
                """INSERT OR REPLACE INTO agent_runs(run_id,packet_id,identity_key,agent_name,started_at,finished_at,status,payload_json)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (item.run_id, item.packet_id, item.identity_key, item.agent_name,
                 item.started_at, item.finished_at, item.status, payload),
            )
            self._db.commit()
            return self._db.total_changes > before

    async def stats(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._stats_sync)

    def _stats_sync(self) -> dict[str, Any]:
        assert self._db is not None
        with self._lock:
            tables = {
                "security_evidence": "security_evidence",
                "graph_edges": "graph_edges",
                "social_mentions": "social_mentions",
                "memory_items": "memory_items",
                "attention_packets": "attention_packets",
                "agent_runs": "agent_runs",
            }
            counts = {key: int(self._db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for key, table in tables.items()}
        return {**counts, "fts_available": self._fts_available}
