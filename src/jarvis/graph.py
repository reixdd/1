from __future__ import annotations

import hashlib
import time
from typing import Any

from .evidence import EvidenceStore
from .metrics import Metrics
from .models import GraphEdgeRecord, Observation, SecurityEvidence

try:
    import networkx as nx
except Exception:  # pragma: no cover - dependency failure is isolated and visible
    nx = None


def _edge_id(source: str, target: str, relation: str, provider: str) -> str:
    raw = "\x1f".join([source, target, relation, provider]).encode("utf-8", "replace")
    return hashlib.sha256(raw).hexdigest()[:32]


class GraphBrain:
    """Timestamped entity relationship evidence with mature graph algorithms."""

    def __init__(self, store: EvidenceStore, metrics: Metrics) -> None:
        self.store = store
        self.metrics = metrics

    async def observe_market(self, obs: Observation) -> None:
        token = f"token:{obs.chain}:{obs.contract}"
        provider = f"provider:{obs.provider}"
        await self.store.upsert_edge(GraphEdgeRecord(
            edge_id=_edge_id(provider, token, "OBSERVED", obs.provider),
            source_node=provider,
            target_node=token,
            relation="OBSERVED",
            provider=obs.provider,
            first_seen_at=obs.observed_at,
            last_seen_at=obs.observed_at,
            identity_key=obs.identity.key,
            attributes={"capability": obs.capability},
        ))
        if obs.pool:
            pool = f"pool:{obs.chain}:{obs.pool}"
            await self.store.upsert_edge(GraphEdgeRecord(
                edge_id=_edge_id(token, pool, "TRADES_ON", obs.provider),
                source_node=token,
                target_node=pool,
                relation="TRADES_ON",
                provider=obs.provider,
                first_seen_at=obs.observed_at,
                last_seen_at=obs.observed_at,
                identity_key=obs.identity.key,
            ))

    async def observe_security(self, evidence: SecurityEvidence) -> None:
        field = evidence.field.lower()
        if not isinstance(evidence.value, str) or not evidence.value.strip():
            return
        relation = None
        node_type = "wallet"
        if "creator" in field or "deployer" in field:
            relation = "DEPLOYED_BY"
        elif field in {"owner_address", "owner"} or "owner_address" in field:
            relation = "OWNED_BY"
        elif "fund" in field and "address" in field:
            relation = "FUNDED_BY"
        if not relation:
            return
        parts = evidence.identity_key.split(":", 2)
        token = f"token:{parts[0]}:{parts[1]}" if len(parts) >= 2 else f"token:{evidence.identity_key}"
        entity = f"{node_type}:{evidence.value.strip()}"
        await self.store.upsert_edge(GraphEdgeRecord(
            edge_id=_edge_id(token, entity, relation, evidence.provider),
            source_node=token,
            target_node=entity,
            relation=relation,
            provider=evidence.provider,
            first_seen_at=evidence.observed_at,
            last_seen_at=evidence.observed_at,
            identity_key=evidence.identity_key,
            evidence_id=evidence.evidence_id,
            attributes={"source_field": evidence.field},
        ))

    async def ingest(self, edge: GraphEdgeRecord) -> None:
        edge.edge_id = _edge_id(edge.source_node, edge.target_node, edge.relation, edge.provider)
        await self.store.upsert_edge(edge)

    async def analyze(self, identity_key: str | None = None) -> dict[str, Any]:
        rows = await self.store.edges(identity_key=identity_key, limit=20000)
        if nx is None:
            return {"available": False, "dependency_error": "networkx unavailable", "edges": len(rows)}
        graph = nx.Graph()
        for edge in rows:
            if graph.has_edge(edge.source_node, edge.target_node):
                graph[edge.source_node][edge.target_node]["weight"] += max(1.0, float(edge.weight))
            else:
                graph.add_edge(edge.source_node, edge.target_node, weight=max(1.0, float(edge.weight)))
        if graph.number_of_nodes() == 0:
            return {
                "available": True,
                "nodes": 0,
                "edges": 0,
                "components": 0,
                "largest_component": 0,
                "communities": 0,
                "note": "No graph evidence has been observed yet.",
            }
        components = list(nx.connected_components(graph))
        communities: list[set[str]] = []
        if graph.number_of_edges() > 0 and graph.number_of_nodes() >= 2:
            try:
                communities = list(nx.community.louvain_communities(graph, weight="weight", seed=0))
            except Exception:
                communities = []
        degree = sorted(graph.degree(weight="weight"), key=lambda pair: pair[1], reverse=True)[:20]
        return {
            "available": True,
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
            "components": len(components),
            "largest_component": max((len(c) for c in components), default=0),
            "communities": len(communities),
            "top_degree": [{"node": node, "weighted_degree": float(weight)} for node, weight in degree],
            "evidence_is_not_verdict": True,
        }

    async def neighborhood(self, identity_key: str) -> dict[str, Any]:
        rows = await self.store.edges(identity_key=identity_key, limit=2000)
        return {
            "identity_key": identity_key,
            "edges": [row.model_dump(mode="json") for row in rows],
            "analysis": await self.analyze(identity_key),
        }
