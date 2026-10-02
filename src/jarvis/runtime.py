from __future__ import annotations

import asyncio
import time
from typing import Any

from .agent_team import AgentTeam
from .attention import AttentionCompiler
from .bus import EventBus
from .capabilities import Capability, CapabilityRegistry
from .config import Settings
from .evidence import EvidenceStore
from .experiments import ExperimentEngine
from .graph import GraphBrain
from .history import ColdArchive
from .memory import MemoryBrain
from .metrics import Metrics
from .models import SecurityEvidence, SocialMention
from .ollama import OllamaCatalog
from .online import OnlineLearner
from .operator import OperatorWorkbench
from .quant import QuantEngine
from .research_ledger import ResearchLedger
from .risk import RiskBrain
from .science import ResearchScientist
from .sense import SenseManager
from .social import SocialBrain
from .tape import MarketTape
from .universe import Universe


class JarvisRuntime:
    """Canonical clean runtime owner.

    Deterministic market/research path:
    SENSE -> BUS -> TAPE -> UNIVERSE -> QUANT -> EXPERIMENT/ONLINE.

    Stage-3 evidence/intelligence consumes canonical observations asynchronously and
    is deliberately non-critical: RISK/GRAPH/SOCIAL/MEMORY/AGENTS/ATTENTION can fail
    without blocking HOT/Quant/Experiments/River/COLD.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings.history_dir.mkdir(parents=True, exist_ok=True)
        self.metrics = Metrics()
        self.registry = CapabilityRegistry()
        self.bus = EventBus(self.metrics)
        self.tape = MarketTape(self.settings.sqlite_path, self.metrics, self.settings.tape_retention_hours)
        self.ledger = ResearchLedger(self.settings.sqlite_path, self.metrics)
        self.evidence = EvidenceStore(self.settings.sqlite_path, self.metrics)
        self.universe = Universe(
            self.metrics,
            self.settings.young_max_age_seconds,
            self.settings.observation_fresh_seconds,
        )
        self.quant = QuantEngine(self.universe, self.metrics)
        self.experiments = ExperimentEngine(self.ledger, self.universe, self.metrics)
        self.online = OnlineLearner(self.ledger, self.metrics)
        self.archive = ColdArchive(
            self.settings.history_dir,
            self.ledger,
            self.metrics,
            export_batch_rows=self.settings.archive_export_batch_rows,
        )
        self.scientist = ResearchScientist(
            self.archive,
            self.metrics,
            min_samples=self.settings.science_min_samples,
        )
        self.sense = SenseManager(self.settings, self.bus, self.universe, self.metrics)
        self.memory = MemoryBrain(self.evidence)
        self.graph = GraphBrain(self.evidence, self.metrics)
        self.social = SocialBrain(self.evidence, self.ledger, self._on_social_mention)
        self.risk = RiskBrain(
            self.settings,
            self.evidence,
            self.metrics,
            self.registry,
            self._on_security_evidence,
        )
        self.ollama = OllamaCatalog(self.settings, self.metrics, self.registry)
        self.agents = AgentTeam(
            self.settings,
            self.metrics,
            self.registry,
            self.ollama,
            self.evidence,
            self.memory,
            self.universe,
            self.quant,
            self.ledger,
            self.risk,
            self.graph,
            self.social,
            self.scientist,
        )
        self.attention = AttentionCompiler(
            self.settings,
            self.evidence,
            self.metrics,
            self.universe,
            self.quant,
            self.ledger,
            self.risk,
            self.graph,
            self.social,
            self.memory,
            self.scientist,
            self.agents,
        )
        # Human-facing composition layer. It owns no provider polling or research state.
        self.operator = OperatorWorkbench(self)
        self._evidence_queue: asyncio.Queue = asyncio.Queue(maxsize=self.settings.evidence_queue_max)
        self._tasks: dict[str, asyncio.Task] = {}
        self.started_at: float | None = None
        self._stopping = False
        self._register_capabilities()

    def _register_capabilities(self) -> None:
        for lane in self.sense.lanes:
            self.registry.register(Capability(
                capability_id=f"sense.{lane.health.lane}",
                brain="SENSE",
                provider=lane.health.provider,
                chains=tuple(self.settings.chains),
                read_only=True,
                freshness="live",
                rate_budget=f"{lane.health.budget_max_calls}/{int(lane.health.budget_window_s)}s",
                required_inputs=(),
            ))
        for cap in (
            Capability("quant.market_features", "QUANT", "local", tuple(self.settings.chains), True, "live"),
            Capability("experiment.prospective", "EXPERIMENT", "local", tuple(self.settings.chains), True, "live"),
            Capability("online.river", "ONLINE", "local", tuple(self.settings.chains), True, "future-label"),
            Capability("science.cold", "SCIENTIST", "DuckDB/Parquet", tuple(self.settings.chains), True, "cold"),
            Capability("risk.goplus.token_security", "RISK", "GoPlus", ("eth", "base", "bsc"), True, "bounded", cost="provider", required_inputs=("contract",), health=("READY" if self.settings.goplus_enabled else "DISABLED")),
            Capability("graph.entity_relationships", "GRAPH", "NetworkX", tuple(self.settings.chains), True, "event-driven"),
            Capability("social.structured_mentions", "SOCIAL", "local/connectors", tuple(self.settings.chains), True, "event-driven"),
            Capability("memory.structured_search", "MEMORY", "SQLite FTS/local", tuple(self.settings.chains), True, "local"),
            Capability("agents.ollama.local_models", "AGENTS", "Ollama", (), True, "runtime-discovered", health="DISCOVERING"),
            Capability("agents.jarvis.manager", "AGENTS", "OpenAI Agents SDK + Ollama", (), True, "on-demand", health=("DISCOVERING" if self.settings.agents_enabled else "DISABLED")),
            Capability("attention.semantic_packets", "ATTENTION", "local", tuple(self.settings.chains), True, "event-driven"),
        ):
            self.registry.register(cap)

    async def start(self) -> None:
        if self.started_at is not None:
            return
        self.started_at = time.time()
        await self.tape.open()
        await self.ledger.open()
        await self.evidence.open()
        await self.archive.open()

        restored = await self.tape.restore_recent(
            since_seconds=max(3600.0, self.settings.young_max_age_seconds * 4), limit=20000
        )
        for obs in restored:
            self.universe.apply(obs, restored=True)
        self.metrics.gauge("restored_observations", len(restored))

        await self.experiments.restore_tracking()
        await self.online.restore()

        self._tasks["market_processor"] = asyncio.create_task(self._processor(), name="jarvis:market_processor")
        self._tasks["stage3_evidence"] = asyncio.create_task(
            self._supervise("stage3_evidence", self._evidence_processor), name="jarvis:stage3_evidence"
        )
        self._tasks["cold_archive"] = asyncio.create_task(
            self._supervise("cold_archive", self.archive.run), name="jarvis:cold_archive"
        )
        self._tasks["scientist"] = asyncio.create_task(
            self._supervise("scientist", self.scientist.run), name="jarvis:scientist"
        )
        self._tasks["risk"] = asyncio.create_task(
            self._supervise("risk", self.risk.run), name="jarvis:risk"
        )
        self._tasks["ollama_catalog"] = asyncio.create_task(
            self._supervise("ollama_catalog", self.ollama.run), name="jarvis:ollama_catalog"
        )
        self._tasks["agents"] = asyncio.create_task(
            self._supervise("agents", self.agents.run), name="jarvis:agents"
        )
        self._tasks["attention"] = asyncio.create_task(
            self._supervise("attention", self.attention.run), name="jarvis:attention"
        )
        for lane in self.sense.lanes:
            self._tasks[f"sense:{lane.health.lane}"] = asyncio.create_task(
                self._supervise(f"sense:{lane.health.lane}", lane.run),
                name=f"jarvis:sense:{lane.health.lane}",
            )

    async def _supervise(self, name: str, runner) -> None:
        backoff = 1.0
        while not self._stopping:
            try:
                await runner()
                return
            except asyncio.CancelledError:
                raise
            except Exception:
                self.metrics.inc(f"supervisor_restart_total:{name}")
                await asyncio.sleep(backoff)
                backoff = min(30.0, backoff * 2)

    async def _processor(self) -> None:
        while True:
            obs = await self.bus.get()
            started = time.perf_counter()
            try:
                inserted = await self.tape.append(obs)
                if not inserted:
                    self.metrics.inc("duplicate_observation_total")
                    continue
                self.metrics.inc("pipeline_tape_accept_total")
                state = self.universe.apply(obs)
                self.metrics.inc("pipeline_universe_apply_total")

                # WARM evidence is a non-blocking side lane. Dropping evidence under overload
                # must never block HOT/Quant/Experiment/Online.
                try:
                    self._evidence_queue.put_nowait(obs)
                    self.metrics.inc("stage3_evidence_enqueued_total")
                except asyncio.QueueFull:
                    self.metrics.inc("stage3_evidence_dropped_total")

                marks = await self.experiments.observe(obs, state)
                for mark in marks:
                    exp = await self.ledger.get_experiment(mark.experiment_id)
                    if exp is not None:
                        await self.online.on_mark(exp, mark)

                snap = self.quant.evaluate(obs)
                if snap is not None:
                    await self.tape.append_quant(snap)
                    self.metrics.inc("pipeline_quant_accept_total")
                    opened = await self.experiments.evaluate(obs, snap, state)
                    for exp in opened:
                        await self.online.on_experiment(exp)
                        await self.attention.notify(exp.identity_key, "prospective_experiment")
                else:
                    self.metrics.inc("pipeline_quant_ineligible_total")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.metrics.inc("pipeline_errors_total")
            finally:
                self.metrics.observe("pipeline_latency_ms", (time.perf_counter() - started) * 1000.0)
                self.bus.task_done()

    async def _evidence_processor(self) -> None:
        while True:
            obs = await self._evidence_queue.get()
            try:
                self.risk.track(obs)
                try:
                    await self.graph.observe_market(obs)
                except Exception:
                    self.metrics.inc("graph_observe_errors_total")
                try:
                    await self.social.observe_market(obs)
                except Exception:
                    self.metrics.inc("social_observe_errors_total")
            except asyncio.CancelledError:
                raise
            except Exception:
                self.metrics.inc("stage3_evidence_errors_total")
            finally:
                self._evidence_queue.task_done()

    async def _on_security_evidence(self, item: SecurityEvidence) -> None:
        try:
            await self.graph.observe_security(item)
        except Exception:
            self.metrics.inc("graph_security_errors_total")
        try:
            await self.memory.remember_security(item)
        except Exception:
            self.metrics.inc("memory_security_errors_total")
        await self.attention.notify(item.identity_key, "security_evidence")

    async def _on_social_mention(self, item: SocialMention) -> None:
        try:
            await self.memory.remember_social(item)
        except Exception:
            self.metrics.inc("memory_social_errors_total")
        await self.attention.notify(item.identity_key, "social_evidence")

    async def stop(self) -> None:
        if self._stopping:
            return
        self._stopping = True
        for lane in self.sense.lanes:
            lane.stop()
        self.archive.stop()
        self.scientist.stop()
        self.attention.stop()
        self.agents.stop()
        await self.risk.close()
        await self.ollama.close()
        for task in self._tasks.values():
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
        await self.sense.close()
        await self.archive.close()
        await self.evidence.close()
        await self.ledger.close()
        await self.tape.close()
        self.started_at = None

    async def status(self) -> dict[str, Any]:
        metrics = self.metrics.snapshot()
        tape = await self.tape.stats()
        universe = self.universe.snapshot(limit=50)
        quant = self.quant.status()
        research = await self.ledger.stats()
        experiments = await self.experiments.status()
        archive = await self.archive.status()
        evidence = await self.evidence.stats()
        pipeline = self.pipeline_status(metrics, tape, universe, quant, research)
        return {
            "application": "JARVIS Clean Research Core",
            "architecture": "clean-step3",
            "research_only": True,
            "execution_enabled": False,
            "started_at": self.started_at,
            "settings": {
                "chains": list(self.settings.chains),
                "young_max_age_seconds": self.settings.young_max_age_seconds,
                "observation_fresh_seconds": self.settings.observation_fresh_seconds,
                "tape_retention_hours": self.settings.tape_retention_hours,
            },
            "pipeline": pipeline,
            "sense": self.sense.status(),
            "tape": tape,
            "universe": {k: v for k, v in universe.items() if k != "items"},
            "quant": quant,
            "experiments": experiments,
            "online": self.online.status(),
            "archive": archive,
            "science": self.scientist.status(),
            "research": research,
            "stage3": {
                "evidence": evidence,
                "risk": self.risk.status(),
                "graph": await self.graph.analyze(),
                "ollama": self.ollama.status(),
                "agents": self.agents.status(),
                "attention": await self.attention.status(),
                "evidence_queue_depth": self._evidence_queue.qsize(),
            },
            "capabilities": self.registry.snapshot(),
            "metrics": metrics,
        }

    @staticmethod
    def pipeline_status(metrics: dict, tape: dict, universe: dict, quant: dict, research: dict) -> dict:
        c = metrics.get("counters", {})
        stages = {
            "provider_observations": int(c.get("provider_observations_total", 0)),
            "event_bus_in": int(c.get("event_bus_in_total", 0)),
            "event_bus_out": int(c.get("event_bus_out_total", 0)),
            "tape_accepts": int(c.get("pipeline_tape_accept_total", 0)),
            "universe_applies": int(c.get("pipeline_universe_apply_total", 0)),
            "universe_eligible": int(universe.get("eligible", 0)),
            "quant_evaluations": int(quant.get("evaluations", 0)),
            "experiments": int(research.get("experiments", 0)),
            "forward_marks": int(research.get("forward_marks", 0)),
            "online_predictions": int(research.get("predictions", 0)),
            "online_labels": int(research.get("labeled", 0)),
            "online_updates": int(research.get("learned", 0)),
        }
        broken_after = None
        order = ["provider_observations", "event_bus_in", "event_bus_out", "tape_accepts", "universe_applies"]
        for previous, current in zip(order, order[1:]):
            if stages[previous] > 0 and stages[current] == 0:
                broken_after = previous
                break
        if broken_after is None and stages["universe_eligible"] > 0 and stages["quant_evaluations"] == 0:
            broken_after = "universe_eligible"
        return {
            "stages": stages,
            "broken_after": broken_after,
            "end_to_end_live": stages["provider_observations"] > 0 and stages["tape_accepts"] > 0 and (
                stages["universe_eligible"] == 0 or stages["quant_evaluations"] > 0
            ),
            "research_note": (
                "Experiments/predictions are prospective. Stage-3 evidence/agents are optional side lanes and "
                "must not affect the deterministic research pipeline."
            ),
        }
