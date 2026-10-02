from __future__ import annotations

import time

import pytest

from jarvis.evidence import EvidenceStore
from jarvis.graph import GraphBrain
from jarvis.memory import MemoryBrain
from jarvis.metrics import Metrics
from jarvis.models import GraphEdgeRecord, SecurityEvidence, SocialMention
from jarvis.research_ledger import ResearchLedger
from jarvis.risk import RiskBrain
from jarvis.social import SocialBrain
from jarvis.capabilities import Capability, CapabilityRegistry
from jarvis.config import Settings


@pytest.mark.asyncio
async def test_risk_preserves_conflicts_and_never_emits_safe_score(tmp_path):
    metrics = Metrics()
    store = EvidenceStore(tmp_path / "db.sqlite3", metrics)
    await store.open()
    settings = Settings.from_env()
    registry = CapabilityRegistry()
    registry.register(Capability("risk.goplus.token_security", "RISK", "GoPlus"))
    brain = RiskBrain(settings, store, metrics, registry)
    identity = "base:0xabc:0xpool"
    try:
        await brain.ingest(SecurityEvidence(identity_key=identity, provider="A", field="owner", value="0x1"))
        await brain.ingest(SecurityEvidence(identity_key=identity, provider="B", field="owner", value="0x2"))
        summary = await brain.summary(identity)
        assert summary["safe_score"] is None
        assert summary["conflicts"][0]["field"] == "owner"
    finally:
        await brain.close()
        await store.close()


@pytest.mark.asyncio
async def test_graph_uses_mature_algorithms_without_fraud_verdict(tmp_path):
    metrics = Metrics()
    store = EvidenceStore(tmp_path / "db.sqlite3", metrics)
    await store.open()
    graph = GraphBrain(store, metrics)
    try:
        await graph.ingest(GraphEdgeRecord(source_node="wallet:a", target_node="token:x", relation="BOUGHT", provider="TEST"))
        await graph.ingest(GraphEdgeRecord(source_node="wallet:b", target_node="token:x", relation="BOUGHT", provider="TEST"))
        out = await graph.analyze()
        assert out["available"] is True
        assert out["nodes"] == 3
        assert out["edges"] == 2
        assert out["components"] == 1
        assert out["evidence_is_not_verdict"] is True
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_social_keeps_project_published_separate_from_independent_and_caller(tmp_path):
    metrics = Metrics()
    db = tmp_path / "db.sqlite3"
    store = EvidenceStore(db, metrics)
    ledger = ResearchLedger(db, metrics)
    await store.open(); await ledger.open()
    social = SocialBrain(store, ledger)
    identity = "sol:token:pool"
    try:
        await social.ingest(SocialMention(identity_key=identity, source_id="project:x", source_type="PROJECT_PUBLISHED", url="https://example.com", independent=False))
        await social.ingest(SocialMention(identity_key=identity, source_id="x:observer", source_type="INDEPENDENT_MENTION", text="independent mention", independent=True))
        await social.ingest(SocialMention(identity_key=identity, source_id="caller:alpha", source_type="CALLER_MENTION", text="caller mention", independent=True))
        out = await social.summary(identity)
        assert out["project_published"] == 1
        assert out["independent_mentions"] == 2
        assert out["caller_mentions"] == 1
        assert out["project_links_are_not_independent_evidence"] is True
    finally:
        await ledger.close(); await store.close()


@pytest.mark.asyncio
async def test_structured_memory_preserves_classification(tmp_path):
    metrics = Metrics()
    store = EvidenceStore(tmp_path / "db.sqlite3", metrics)
    await store.open()
    memory = MemoryBrain(store)
    try:
        item = SecurityEvidence(identity_key="eth:0xabc:-", provider="TEST", field="owner", value="0x1")
        remembered = await memory.remember_security(item)
        assert remembered.classification == "UNVERIFIED_CLAIM"
        rows = await memory.search("owner")
        assert rows["items"][0]["classification"] == "UNVERIFIED_CLAIM"
    finally:
        await store.close()
