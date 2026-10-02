from __future__ import annotations

import hashlib
import statistics
from typing import Any, Awaitable, Callable

from .evidence import EvidenceStore
from .models import Observation, SocialMention
from .research_ledger import ResearchLedger


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8", "replace")).hexdigest()[:32]


class SocialBrain:
    """Keeps project-published links distinct from independent/caller observations."""

    def __init__(
        self,
        store: EvidenceStore,
        ledger: ResearchLedger,
        on_mention: Callable[[SocialMention], Awaitable[None]] | None = None,
    ) -> None:
        self.store = store
        self.ledger = ledger
        self.on_mention = on_mention

    async def observe_market(self, obs: Observation) -> list[SocialMention]:
        links = obs.provenance.get("profile_links") if isinstance(obs.provenance, dict) else None
        if not isinstance(links, list):
            return []
        inserted: list[SocialMention] = []
        for raw in links[:50]:
            if isinstance(raw, str):
                url = raw
                label = "project_link"
                platform = None
            elif isinstance(raw, dict):
                url = str(raw.get("url") or "").strip()
                label = str(raw.get("label") or raw.get("type") or "project_link").strip()
                platform = str(raw.get("type") or "").strip() or None
            else:
                continue
            if not url:
                continue
            mention = SocialMention(
                mention_id=_stable_id(obs.identity.key, "PROJECT_PUBLISHED", url),
                identity_key=obs.identity.key,
                source_id=f"project:{obs.identity.key}",
                source_type="PROJECT_PUBLISHED",
                observed_at=obs.observed_at,
                text=f"Project-published {label}",
                url=url,
                platform=platform,
                independent=False,
                provenance={"provider": obs.provider, "source_event_id": obs.event_id},
            )
            if await self.store.insert_social(mention):
                inserted.append(mention)
                if self.on_mention:
                    await self.on_mention(mention)
        return inserted

    async def ingest(self, mention: SocialMention) -> bool:
        inserted = await self.store.insert_social(mention)
        if inserted and self.on_mention:
            await self.on_mention(mention)
        return inserted

    async def summary(self, identity_key: str) -> dict[str, Any]:
        rows = await self.store.social_for(identity_key, 500)
        project = [r for r in rows if r.source_type == "PROJECT_PUBLISHED"]
        independent = [r for r in rows if r.independent or r.source_type == "INDEPENDENT_MENTION"]
        callers = [r for r in rows if r.source_type == "CALLER_MENTION"]
        return {
            "identity_key": identity_key,
            "mentions": len(rows),
            "project_published": len(project),
            "independent_mentions": len(independent),
            "caller_mentions": len(callers),
            "independent_sources": len({r.source_id for r in independent}),
            "project_links_are_not_independent_evidence": True,
            "items": [r.model_dump(mode="json") for r in rows[:100]],
        }

    async def caller_summary(self, source_id: str) -> dict[str, Any]:
        rows = [r for r in await self.store.social_by_source(source_id, 1000) if r.source_type == "CALLER_MENTION"]
        returns: list[float] = []
        matured = 0
        for mention in rows[:200]:
            outcomes = await self.ledger.outcomes_after(mention.identity_key, mention.observed_at, horizon_seconds=900)
            if outcomes:
                matured += 1
                ret = outcomes[0].get("return_pct")
                if isinstance(ret, (int, float)):
                    returns.append(float(ret))
        return {
            "source_id": source_id,
            "mentions": len(rows),
            "unique_identities": len({r.identity_key for r in rows}),
            "matured_15m_outcomes": matured,
            "median_15m_market_return_pct": statistics.median(returns) if returns else None,
            "outcome_n": len(returns),
            "note": "Caller history is descriptive evidence only; it is not a recommendation or reliability score.",
        }
