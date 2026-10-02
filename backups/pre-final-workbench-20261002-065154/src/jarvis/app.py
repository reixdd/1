from __future__ import annotations

from fastapi import FastAPI, Query, Request

from . import __version__
from .lifecycle import lifespan
from .models import GraphEdgeRecord, SecurityEvidence, SocialMention


def create_app() -> FastAPI:
    app = FastAPI(
        title="JARVIS Clean Research Core",
        version=__version__,
        description=(
            "Step 3: proven SENSE/Quant/Experiment/River/COLD pipeline plus optional "
            "Risk/Graph/Social/Memory/Agents/Attention evidence intelligence. Research only."
        ),
        lifespan=lifespan,
    )

    @app.get("/")
    async def root():
        return {
            "name": "JARVIS Clean Research Core",
            "version": __version__,
            "step": 3,
            "research_only": True,
            "docs": "/docs",
            "status": "/api/status",
            "pipeline": "/api/pipeline",
            "research": "/api/research",
            "evidence": "/api/evidence",
            "attention": "/api/attention",
        }

    @app.get("/health")
    async def health(request: Request):
        runtime = request.app.state.runtime
        return {"ok": True, "started_at": runtime.started_at, "architecture": "clean-step3"}

    @app.get("/api/status")
    async def status(request: Request):
        return await request.app.state.runtime.status()

    @app.get("/api/pipeline")
    async def pipeline(request: Request):
        status = await request.app.state.runtime.status()
        return status["pipeline"]

    @app.get("/api/providers")
    async def providers(request: Request):
        return request.app.state.runtime.sense.status()

    @app.get("/api/universe")
    async def universe(request: Request, limit: int = Query(200, ge=1, le=2000)):
        return request.app.state.runtime.universe.snapshot(limit=limit)

    @app.get("/api/quant")
    async def quant(request: Request, limit: int = Query(100, ge=1, le=1000)):
        runtime = request.app.state.runtime
        return {"status": runtime.quant.status(), "items": runtime.quant.recent(limit)}

    @app.get("/api/tape")
    async def tape(request: Request, limit: int = Query(100, ge=1, le=1000)):
        runtime = request.app.state.runtime
        return {"status": await runtime.tape.stats(), "items": await runtime.tape.recent(limit)}

    @app.get("/api/research")
    async def research(request: Request):
        runtime = request.app.state.runtime
        return {
            "experiments": await runtime.experiments.status(),
            "online": runtime.online.status(),
            "archive": await runtime.archive.status(),
            "science": runtime.scientist.status(),
        }

    @app.get("/api/research/experiments")
    async def experiments(request: Request, limit: int = Query(100, ge=1, le=1000)):
        runtime = request.app.state.runtime
        return {
            "status": await runtime.experiments.status(),
            "items": await runtime.ledger.recent_experiments(limit),
        }

    @app.get("/api/research/online")
    async def online(request: Request):
        runtime = request.app.state.runtime
        stats = await runtime.ledger.stats()
        return {"status": runtime.online.status(), "ledger": stats}

    @app.get("/api/research/science")
    async def science(request: Request):
        return request.app.state.runtime.scientist.status()

    @app.get("/api/research/archive")
    async def archive(request: Request):
        return await request.app.state.runtime.archive.status()

    @app.get("/api/evidence")
    async def evidence(request: Request):
        runtime = request.app.state.runtime
        return {
            "store": await runtime.evidence.stats(),
            "risk": runtime.risk.status(),
            "graph": await runtime.graph.analyze(),
            "social": {"structured": True, "project_vs_independent_separated": True},
            "memory": {"structured_classes": ["FACT", "OBSERVATION", "HYPOTHESIS", "UNVERIFIED_CLAIM", "AGENT_CONCLUSION"]},
        }

    @app.get("/api/evidence/risk")
    async def risk(request: Request, identity_key: str):
        return await request.app.state.runtime.risk.summary(identity_key)

    @app.post("/api/evidence/risk")
    async def risk_ingest(request: Request, item: SecurityEvidence):
        inserted = await request.app.state.runtime.risk.ingest(item)
        return {"inserted": inserted, "research_evidence_only": True}

    @app.get("/api/evidence/graph")
    async def graph(request: Request, identity_key: str | None = None):
        runtime = request.app.state.runtime
        return await runtime.graph.neighborhood(identity_key) if identity_key else await runtime.graph.analyze()

    @app.post("/api/evidence/graph")
    async def graph_ingest(request: Request, item: GraphEdgeRecord):
        await request.app.state.runtime.graph.ingest(item)
        return {"inserted": True, "evidence_is_not_verdict": True}

    @app.get("/api/evidence/social")
    async def social(request: Request, identity_key: str):
        return await request.app.state.runtime.social.summary(identity_key)

    @app.post("/api/evidence/social")
    async def social_ingest(request: Request, item: SocialMention):
        inserted = await request.app.state.runtime.social.ingest(item)
        return {"inserted": inserted, "project_links_are_not_independent": True}

    @app.get("/api/evidence/caller")
    async def caller(request: Request, source_id: str):
        return await request.app.state.runtime.social.caller_summary(source_id)

    @app.get("/api/memory/search")
    async def memory_search(request: Request, q: str, limit: int = Query(50, ge=1, le=500)):
        return await request.app.state.runtime.memory.search(q, limit)

    @app.get("/api/attention")
    async def attention(request: Request, limit: int = Query(100, ge=1, le=1000)):
        runtime = request.app.state.runtime
        return {
            "status": await runtime.attention.status(),
            "items": [p.model_dump(mode="json") for p in await runtime.evidence.recent_attention(limit)],
        }

    @app.get("/api/agents")
    async def agents(request: Request):
        return request.app.state.runtime.agents.status()

    @app.get("/api/models")
    async def models(request: Request):
        return request.app.state.runtime.ollama.status()

    @app.get("/api/capabilities")
    async def capabilities(request: Request):
        return request.app.state.runtime.registry.snapshot()

    @app.get("/api/metrics")
    async def metrics(request: Request):
        return request.app.state.runtime.metrics.snapshot()

    return app


app = create_app()
