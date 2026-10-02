from __future__ import annotations

from typing import Any

from .evidence import EvidenceStore
from .models import AgentRunRecord, AttentionPacket, MemoryItem, SecurityEvidence, SocialMention


class MemoryBrain:
    """Structured memory; classifications are never flattened into generic notes."""

    def __init__(self, store: EvidenceStore) -> None:
        self.store = store

    async def remember_security(self, item: SecurityEvidence) -> MemoryItem:
        memory = MemoryItem(
            identity_key=item.identity_key,
            classification="UNVERIFIED_CLAIM" if item.classification == "CLAIM" else "OBSERVATION",
            content=f"{item.provider} reported {item.field}={item.value!r}",
            observed_at=item.observed_at,
            source=f"risk:{item.provider}",
            confidence=item.confidence,
            related_ids=[item.evidence_id],
            provenance={"field": item.field, "classification": item.classification},
        )
        await self.store.insert_memory(memory)
        return memory

    async def remember_social(self, item: SocialMention) -> MemoryItem:
        classification = "FACT" if item.source_type == "PROJECT_PUBLISHED" else "OBSERVATION"
        memory = MemoryItem(
            identity_key=item.identity_key,
            classification=classification,
            content=(item.text or item.url or f"{item.source_type} from {item.source_id}"),
            observed_at=item.observed_at,
            source=f"social:{item.source_id}",
            confidence="DIRECT_OBSERVATION" if item.independent else "SOURCE_PUBLISHED",
            related_ids=[item.mention_id],
            provenance={"source_type": item.source_type, "platform": item.platform, "url": item.url},
        )
        await self.store.insert_memory(memory)
        return memory

    async def remember_attention(self, packet: AttentionPacket) -> MemoryItem:
        memory = MemoryItem(
            identity_key=packet.identity_key,
            classification="OBSERVATION",
            content="; ".join(packet.what_changed[:4]) or "Attention packet compiled",
            observed_at=packet.created_at,
            source="attention_compiler",
            confidence="DETERMINISTIC_COMPILATION",
            related_ids=[packet.packet_id, *packet.evidence_ids[:20]],
            provenance={"status": packet.status, "triggers": packet.trigger_reasons},
        )
        await self.store.insert_memory(memory)
        return memory

    async def remember_agent(self, run: AgentRunRecord) -> MemoryItem | None:
        if not run.output:
            return None
        memory = MemoryItem(
            identity_key=run.identity_key,
            classification="AGENT_CONCLUSION",
            content=run.output[:8000],
            observed_at=run.finished_at or run.started_at,
            source=f"agent:{run.agent_name}",
            confidence="AGENT_INTERPRETATION_NOT_FACT",
            related_ids=[run.run_id, run.packet_id],
            provenance={"model": run.model, "status": run.status},
        )
        await self.store.insert_memory(memory)
        return memory

    async def search(self, query: str, limit: int = 50) -> dict[str, Any]:
        rows = await self.store.search_memory(query, limit)
        return {
            "query": query,
            "items": [row.model_dump(mode="json") for row in rows],
            "note": "Structured classes are preserved. Search does not upgrade claims or agent conclusions into facts.",
        }
