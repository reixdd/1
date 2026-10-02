from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Any

from .agent_team import AgentTeam
from .evidence import EvidenceStore
from .graph import GraphBrain
from .memory import MemoryBrain
from .metrics import Metrics
from .models import AttentionPacket
from .quant import QuantEngine
from .research_ledger import ResearchLedger
from .risk import RiskBrain
from .science import ResearchScientist
from .social import SocialBrain
from .universe import Universe


class AttentionCompiler:
    """Compiles semantic research changes; raw plumbing stays in diagnostics/metrics."""

    def __init__(self, settings, store: EvidenceStore, metrics: Metrics, universe: Universe,
                 quant: QuantEngine, ledger: ResearchLedger, risk: RiskBrain, graph: GraphBrain,
                 social: SocialBrain, memory: MemoryBrain, scientist: ResearchScientist,
                 agents: AgentTeam) -> None:
        self.settings = settings
        self.store = store
        self.metrics = metrics
        self.universe = universe
        self.quant = quant
        self.ledger = ledger
        self.risk = risk
        self.graph = graph
        self.social = social
        self.memory = memory
        self.scientist = scientist
        self.agents = agents
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1024)
        self._reasons: dict[str, set[str]] = defaultdict(set)
        self._queued: set[str] = set()
        self._last_packet_at: dict[str, float] = {}
        self._stop = asyncio.Event()

    async def notify(self, identity_key: str, reason: str) -> None:
        if not identity_key:
            return
        self._reasons[identity_key].add(str(reason))
        if identity_key in self._queued:
            self.metrics.inc("attention_coalesced_total")
            return
        try:
            self._queue.put_nowait(identity_key)
            self._queued.add(identity_key)
            self.metrics.inc("attention_candidates_total")
        except asyncio.QueueFull:
            self.metrics.inc("attention_candidates_dropped_total")

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        while not self._stop.is_set():
            try:
                identity_key = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError:
                continue
            try:
                await asyncio.sleep(self.settings.attention_debounce_seconds)
                now = time.time()
                if now - self._last_packet_at.get(identity_key, 0.0) < self.settings.attention_cooldown_seconds:
                    self.metrics.inc("attention_cooldown_suppressed_total")
                    continue
                packet = await self.compile(identity_key, sorted(self._reasons.pop(identity_key, set())))
                if packet is not None:
                    await self.store.insert_attention(packet)
                    await self.memory.remember_attention(packet)
                    await self.agents.submit(packet)
                    self._last_packet_at[identity_key] = packet.created_at
            except asyncio.CancelledError:
                raise
            except Exception:
                self.metrics.inc("attention_compile_errors_total")
            finally:
                self._queued.discard(identity_key)
                self._queue.task_done()

    async def compile(self, identity_key: str, reasons: list[str]) -> AttentionPacket | None:
        state = self.universe.get(identity_key)
        risk = await self.risk.summary(identity_key)
        social = await self.social.summary(identity_key)
        graph = await self.graph.neighborhood(identity_key)
        experiments = [r for r in await self.ledger.recent_experiments(1000) if r.get("identity_key") == identity_key]
        base_rate = await self.ledger.label_base_rate()
        snaps = [r for r in self.quant.recent(1000) if r.get("identity_key") == identity_key]
        latest_quant = snaps[0] if snaps else None

        what_changed: list[str] = []
        if "prospective_experiment" in reasons:
            what_changed.append("A prospective research condition transitioned false→true and opened a frozen experiment.")
        if "security_evidence" in reasons:
            what_changed.append("New timestamped security-provider evidence arrived.")
        if "social_evidence" in reasons:
            what_changed.append("New social/source evidence arrived.")
        if not what_changed:
            what_changed.append("Canonical research evidence changed enough to recompile this packet.")

        why: list[str] = []
        if experiments:
            why.append(f"{len(experiments)} prospective experiment(s) are recorded for this identity.")
        if social.get("independent_mentions", 0):
            why.append(f"{social['independent_mentions']} independent social mention(s) are recorded separately from project links.")
        if risk.get("evidence_count", 0):
            why.append(f"{risk['evidence_count']} timestamped security evidence item(s) are available for cross-checking.")
        if latest_quant and latest_quant.get("provider_count", 0) >= 2:
            why.append("The latest Quant snapshot has observations from multiple market providers.")

        counter: list[str] = []
        if risk.get("conflicts"):
            counter.append(f"Security providers/observations conflict on {len(risk['conflicts'])} field(s).")
        if social.get("project_published", 0) and not social.get("independent_mentions", 0):
            counter.append("Social evidence is currently project-published only; no independent mention is recorded.")
        if latest_quant and isinstance(latest_quant.get("provider_disagreement"), (int, float)):
            if float(latest_quant["provider_disagreement"]) > 0.20:
                counter.append("Market providers materially disagree on the latest observed price.")
        science = self.scientist.status()
        if science.get("state") not in {"COMPLETE"}:
            counter.append(f"COLD Scientist state is {science.get('state')}; validated evidence is not complete.")

        unknowns: list[str] = []
        if risk.get("evidence_count", 0) == 0:
            unknowns.append("No independent token-security provider evidence is recorded yet.")
        if social.get("independent_mentions", 0) == 0:
            unknowns.append("No independent social mention is recorded yet.")
        if graph.get("analysis", {}).get("edges", 0) <= 2:
            unknowns.append("Entity graph evidence is still sparse.")

        status = "MIXED" if counter else ("INCOMPLETE" if unknowns else "EVIDENCE_UPDATED")
        evidence_ids = [row.get("evidence_id") for row in risk.get("evidence", []) if row.get("evidence_id")]
        packet = AttentionPacket(
            identity_key=identity_key,
            trigger_reasons=reasons,
            what_changed=what_changed,
            why_it_matters_for_research=why or ["A prospective evidence packet exists, but current support remains limited."],
            counter_evidence=counter,
            historical_context={
                "prospective_experiments_for_identity": len(experiments),
                "scientist_state": science.get("state"),
                "scientist_sample_n": science.get("sample_n"),
                "latest_market": state.as_dict() if state else None,
            },
            base_rate={
                "label": "15m liquidity retention >=75% of T0",
                **base_rate,
            },
            unknowns=unknowns,
            status=status,
            evidence_ids=evidence_ids[:100],
        )
        return packet

    async def status(self) -> dict[str, Any]:
        return {
            "queue_depth": self._queue.qsize(),
            "queued_identities": len(self._queued),
            "recent_packets": len(await self.store.recent_attention(1000)),
            "operator_mode_semantic_only": True,
            "raw_provider_plumbing_is_diagnostics": True,
        }
