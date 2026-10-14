from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

from .capabilities import CapabilityRegistry
from .evidence import EvidenceStore
from .graph import GraphBrain
from .memory import MemoryBrain
from .metrics import Metrics
from .models import AgentRunRecord, AttentionPacket
from .ollama import OllamaCatalog
from .quant import QuantEngine
from .research_ledger import ResearchLedger
from .risk import RiskBrain
from .science import ResearchScientist
from .social import SocialBrain
from .universe import Universe


ROLE_CAPABILITIES = {
    "SCOUT": ("market_context", "research_context"),
    "INVESTIGATOR": ("risk_context", "graph_context", "memory_search"),
    "SOCIAL": ("social_context", "memory_search"),
    "CALLER": ("caller_context",),
    "QUANT_SKEPTIC": ("market_context", "research_context", "risk_context", "science_context"),
    "REVIEWER": ("memory_search", "risk_context", "social_context", "science_context"),
    "SCIENTIST": ("research_context", "science_context"),
}


@dataclass(slots=True)
class AgentContext:
    identity_key: str
    universe: Universe
    quant: QuantEngine
    ledger: ResearchLedger
    risk: RiskBrain
    graph: GraphBrain
    social: SocialBrain
    memory: MemoryBrain
    scientist: ResearchScientist


class AgentTeam:
    """One optional OpenAI Agents SDK runtime over runtime-discovered local Ollama models.

    Agents consume canonical state through bounded tools. They never own market polling,
    Quant, experiment creation, online learning, or transaction execution.
    """

    def __init__(self, settings, metrics: Metrics, registry: CapabilityRegistry, catalog: OllamaCatalog,
                 store: EvidenceStore, memory: MemoryBrain, universe: Universe, quant: QuantEngine,
                 ledger: ResearchLedger, risk: RiskBrain, graph: GraphBrain, social: SocialBrain,
                 scientist: ResearchScientist) -> None:
        self.settings = settings
        self.metrics = metrics
        self.registry = registry
        self.catalog = catalog
        self.store = store
        self.memory = memory
        self.universe = universe
        self.quant = quant
        self.ledger = ledger
        self.risk = risk
        self.graph = graph
        self.social = social
        self.scientist = scientist
        self._queue: asyncio.Queue[AttentionPacket] = asyncio.Queue(maxsize=256)
        self._stop = asyncio.Event()
        self._sdk_error: str | None = None
        self._last_error: str | None = None
        self._last_run_at: float | None = None
        self._runs = 0
        self._team_cache: tuple[tuple[str | None, str | None], Any] | None = None
        self._dit_slots = asyncio.Semaphore(3)  # bounded shared JARVIS-lite admission

    async def submit(self, packet: AttentionPacket) -> None:
        if not self.settings.agents_enabled:
            return
        try:
            self._queue.put_nowait(packet)
            self.metrics.inc("agent_jobs_submitted_total")
        except asyncio.QueueFull:
            self.metrics.inc("agent_jobs_dropped_total")

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        while not self._stop.is_set():
            try:
                packet = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError:
                continue
            try:
                await self._run_packet(packet)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
                self.metrics.inc("agent_job_errors_total")
            finally:
                self._queue.task_done()

    def _imports(self):
        try:
            from agents import (
                Agent,
                AsyncOpenAI,
                OpenAIChatCompletionsModel,
                Runner,
                RunContextWrapper,
                function_tool,
                set_tracing_disabled,
            )
            return Agent, AsyncOpenAI, OpenAIChatCompletionsModel, Runner, RunContextWrapper, function_tool, set_tracing_disabled
        except Exception as exc:
            self._sdk_error = f"{type(exc).__name__}: {exc}"
            return None

    def _team(self):
        selection = self.catalog.selection()
        cache_key = (selection.get("fast"), selection.get("deep"))
        if self._team_cache and self._team_cache[0] == cache_key:
            return self._team_cache[1]
        imported = self._imports()
        if imported is None or not selection.get("fast") or not selection.get("deep"):
            return None
        Agent, AsyncOpenAI, OpenAIChatCompletionsModel, Runner, RunContextWrapper, function_tool, set_tracing_disabled = imported
        set_tracing_disabled(True)
        client = AsyncOpenAI(base_url=f"{self.settings.ollama_url.rstrip('/')}/v1/", api_key="ollama")
        fast_model = OpenAIChatCompletionsModel(model=selection["fast"], openai_client=client)
        deep_model = OpenAIChatCompletionsModel(model=selection["deep"], openai_client=client)

        @function_tool
        async def market_context(ctx: RunContextWrapper[AgentContext]) -> dict[str, Any]:
            """Read the canonical current market and recent deterministic Quant state for the selected identity."""
            state = ctx.context.universe.get(ctx.context.identity_key)
            snaps = [r for r in ctx.context.quant.recent(500) if r.get("identity_key") == ctx.context.identity_key]
            return {"market": state.as_dict() if state else None, "recent_quant": snaps[:20]}

        @function_tool
        async def research_context(ctx: RunContextWrapper[AgentContext]) -> dict[str, Any]:
            """Read prospective experiment history and online-learning base rates; do not modify them."""
            rows = [r for r in await ctx.context.ledger.recent_experiments(1000) if r.get("identity_key") == ctx.context.identity_key]
            return {"experiments": rows[:50], "label_base_rate": await ctx.context.ledger.label_base_rate()}

        @function_tool
        async def risk_context(ctx: RunContextWrapper[AgentContext]) -> dict[str, Any]:
            """Read timestamped security claims, conflicts, and unknowns. No safety score exists."""
            return await ctx.context.risk.summary(ctx.context.identity_key)

        @function_tool
        async def graph_context(ctx: RunContextWrapper[AgentContext]) -> dict[str, Any]:
            """Read timestamped entity relationships and graph structure as evidence, never as an automatic fraud verdict."""
            return await ctx.context.graph.neighborhood(ctx.context.identity_key)

        @function_tool
        async def social_context(ctx: RunContextWrapper[AgentContext]) -> dict[str, Any]:
            """Read social evidence, preserving project-published versus independent mentions."""
            return await ctx.context.social.summary(ctx.context.identity_key)

        @function_tool
        async def caller_context(ctx: RunContextWrapper[AgentContext], source_id: str) -> dict[str, Any]:
            """Read descriptive recurring-source history for a caller/source id. This is not a reliability score."""
            return await ctx.context.social.caller_summary(source_id)

        @function_tool
        async def memory_search(ctx: RunContextWrapper[AgentContext], query: str) -> dict[str, Any]:
            """Search structured memory while preserving FACT/OBSERVATION/HYPOTHESIS/CLAIM/AGENT_CONCLUSION classes."""
            return await ctx.context.memory.search(query, 40)

        @function_tool
        async def science_context(ctx: RunContextWrapper[AgentContext]) -> dict[str, Any]:
            """Read COLD Scientist validation state. Never deploy a rule or change live hypotheses."""
            return ctx.context.scientist.status()

        tools = {
            "market_context": market_context,
            "research_context": research_context,
            "risk_context": risk_context,
            "graph_context": graph_context,
            "social_context": social_context,
            "caller_context": caller_context,
            "memory_search": memory_search,
            "science_context": science_context,
        }

        common = (
            "You are a bounded JARVIS research specialist. Use only the supplied read-only research tools. "
            "Separate fact, provider claim, uncertainty and inference. Do not recommend buying, selling, swapping, "
            "position sizing, price targets, or transaction actions. Do not treat project-published social links as "
            "independent corroboration. Prefer prospective evidence and historical base rates."
        )
        specs = {
            "SCOUT": (fast_model, "Triage the evidence quickly and identify what deserves deeper research."),
            "INVESTIGATOR": (deep_model, "Gather bounded risk, graph and memory evidence and surface conflicts/unknowns."),
            "SOCIAL": (fast_model, "Interpret social/narrative evidence while separating project-published from independent mentions."),
            "CALLER": (fast_model, "Study recurring source/caller history descriptively using only prospective recorded outcomes."),
            "QUANT_SKEPTIC": (deep_model, "Attack the strongest apparent thesis: seek base-rate neglect, provider disagreement, weak N, regime mismatch and counterexamples."),
            "REVIEWER": (deep_model, "Review evidence quality, agent conclusions and missing information. Flag unsupported claims."),
            "SCIENTIST": (deep_model, "Interpret validated COLD research and propose falsifiable follow-up hypotheses; never deploy them."),
        }
        specialists = {}
        for role, (model, instructions) in specs.items():
            specialists[role] = Agent(
                name=role,
                instructions=f"{common}\n\nROLE: {instructions}",
                model=model,
                tools=[tools[name] for name in ROLE_CAPABILITIES[role]],
            )
        manager_tools = [
            specialists[role].as_tool(
                tool_name=f"ask_{role.lower()}",
                tool_description=f"Ask {role} for bounded specialist research on the current attention packet.",
            )
            for role in specialists
        ]
        manager = Agent(
            name="JARVIS",
            instructions=(
                f"{common}\n\nYou are the manager and attention compiler, not a market-data processor. "
                "Call only specialists needed for the packet. Strong apparent theses require a QUANT_SKEPTIC call. "
                "In background packet analysis, return compact WHAT CHANGED / WHY IT MATTERS FOR RESEARCH / "
                "COUNTER-EVIDENCE / HISTORICAL CONTEXT / UNKNOWN sections. In direct operator conversation, sound like "
                "a calm, fast research copilot: lead with the answer, keep routine replies short, highlight only material "
                "changes, and use specialist agents invisibly. Never give a transaction or action recommendation."
            ),
            model=deep_model,
            tools=manager_tools,
        )
        # Lightweight DIT research reuses the existing fast Ollama model and
        # existing bounded JARVIS specialists; it never loads another model.
        # Ordinary JARVIS fast/deep behavior remains unchanged.
        manager_lite = Agent(
            name="JARVIS_LITE",
            instructions=(
                f"{common}\n\nThis is a compact, read-only research request from DIT. "
                "Prefer one short, sourced answer. Call at most one specialist when "
                "external evidence is needed; otherwise state uncertainty. "
                "Never initiate trading, wallet changes, or provider polling."
            ),
            model=fast_model,
            tools=[
                specialists[role].as_tool(
                    tool_name=f"ask_{role.lower()}",
                    tool_description=f"Ask the existing {role} agent for bounded read-only research.",
                )
                for role in ("SCOUT", "SOCIAL")
            ],
        )
        team = {"Runner": Runner, "manager": manager, "manager_lite": manager_lite, "models": selection,
                "Agent": Agent, "OpenAIChatCompletionsModel": OpenAIChatCompletionsModel, "client": client}
        self._team_cache = (cache_key, team)
        self._sdk_error = None
        return team

    async def ask(self, message: str, identity_key: str = "", mode: str = "fast",
                  operator_context: dict[str, Any] | None = None, timeout_seconds: float | None = None,
                  model_override: str | None = None) -> str:
        """Conversational operator entry point over the same bounded manager team.

        This never owns provider polling or market state. The selected identity and a
        compact operator snapshot are injected as context; specialists remain internal.
        """
        text = str(message or "").strip()
        if not text:
            raise ValueError("message is required")
        if len(text) > 6000:
            text = text[:6000]
        team = self._team()
        if team is None:
            raise RuntimeError("JARVIS local agent team is unavailable; check Ollama and /api/models")
        key = str(identity_key or "").strip()
        context = AgentContext(
            identity_key=key, universe=self.universe, quant=self.quant, ledger=self.ledger,
            risk=self.risk, graph=self.graph, social=self.social, memory=self.memory, scientist=self.scientist,
        )
        selected = self.universe.get(key) if key else None
        prompt_context = {
            "selected_market": selected.as_dict() if selected else None,
            "operator_snapshot": operator_context or {},
            "instruction": (
                "Answer the operator directly and concisely. Lead with the newest material fact or the answer. "
                "Use specialists invisibly when they add evidence. Clearly separate observed facts, provider claims, "
                "inference, counter-evidence and unknowns. Do not give transaction instructions or buy/sell/position advice."
            ),
        }
        prompt = (
            "OPERATOR CONTEXT:\n" + json.dumps(prompt_context, separators=(",", ":"), default=str)[:24000]
            + "\n\nUSER:\n" + text
        )
        lite = str(mode).lower() == "lite"
        chosen_manager = team["manager_lite"] if lite else team["manager"]
        if model_override and lite:
            installed = {str(row.get("name")) for row in self.catalog.models if row.get("name")}
            if model_override not in installed:
                raise ValueError("Requested DIT model is not installed locally")
            selected_model = team["OpenAIChatCompletionsModel"](
                model=model_override, openai_client=team["client"]
            )
            template = team["manager_lite"]
            chosen_manager = team["Agent"](
                name="JARVIS_DIT_" + str(identity_key or "AGENT").replace(".", "_")[:40],
                instructions=template.instructions,
                model=selected_model,
                tools=template.tools,
            )
        timeout = timeout_seconds or (50.0 if lite else 180.0 if str(mode).lower() == "deep" else 75.0)
        started = time.perf_counter()
        acquired = False
        try:
            if lite:
                await asyncio.wait_for(self._dit_slots.acquire(), timeout=10.0)
                acquired = True
            result = await asyncio.wait_for(
                team["Runner"].run(
                    starting_agent=chosen_manager, input=prompt, context=context,
                    max_turns=4 if lite else 14 if str(mode).lower() == "deep" else 9,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError as exc:
            self.metrics.inc("operator_chat_timeouts_total")
            raise RuntimeError(f"JARVIS admission or inference timed out (limit {int(timeout)}s)") from exc
        finally:
            if acquired:
                self._dit_slots.release()
        self.metrics.inc("operator_chat_runs_total")
        self.metrics.observe("operator_chat_latency_ms", (time.perf_counter() - started) * 1000.0)
        answer = str(result.final_output or "").strip()
        return answer or "I do not have enough evidence to answer that yet."

    async def _run_packet(self, packet: AttentionPacket) -> None:
        team = self._team()
        if team is None:
            self.metrics.inc("agent_jobs_skipped_unavailable_total")
            return
        started = time.perf_counter()
        context = AgentContext(
            identity_key=packet.identity_key,
            universe=self.universe,
            quant=self.quant,
            ledger=self.ledger,
            risk=self.risk,
            graph=self.graph,
            social=self.social,
            memory=self.memory,
            scientist=self.scientist,
        )
        run = AgentRunRecord(
            packet_id=packet.packet_id,
            identity_key=packet.identity_key,
            agent_name="JARVIS",
            model=team["models"].get("deep"),
        )
        try:
            prompt = json.dumps(packet.model_dump(mode="json"), separators=(",", ":"))
            result = await team["Runner"].run(
                starting_agent=team["manager"],
                input=f"Analyze this deterministic attention packet:\n{prompt}",
                context=context,
                max_turns=12,
            )
            run.status = "COMPLETE"
            run.output = str(result.final_output or "")[:12000]
            self.registry.success("agents.jarvis.manager", (time.perf_counter() - started) * 1000.0)
        except Exception as exc:
            run.status = "ERROR"
            run.error = f"{type(exc).__name__}: {str(exc)[:1000]}"
            self._last_error = run.error
            self.registry.failure("agents.jarvis.manager", exc)
            self.metrics.inc("agent_job_errors_total")
        finally:
            run.finished_at = time.time()
            run.latency_ms = (time.perf_counter() - started) * 1000.0
            await self.store.insert_agent_run(run)
            await self.memory.remember_agent(run)
            self.metrics.observe("agent_job_latency_ms", run.latency_ms)
            self._runs += 1
            self._last_run_at = run.finished_at

    def status(self) -> dict[str, Any]:
        selection = self.catalog.selection()
        return {
            "enabled": self.settings.agents_enabled,
            "sdk_available": self._imports() is not None,
            "sdk_error": self._sdk_error,
            "ollama_available": bool(self.catalog.models),
            "models": selection,
            "manager": "JARVIS",
            "specialists": list(ROLE_CAPABILITIES),
            "role_capabilities": {k: list(v) for k, v in ROLE_CAPABILITIES.items()},
            "queue_depth": self._queue.qsize(),
            "runs": self._runs,
            "last_run_at": self._last_run_at,
            "last_error": self._last_error,
            "market_pipeline_dependency": False,
            "research_only": True,
        }
