from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import AsyncIterator, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from .lifecycle import lifespan
from .models import GraphEdgeRecord, SecurityEvidence, SocialMention


class WatchRequest(BaseModel):
    identity_key: str = Field(min_length=3, max_length=300)
    watching: bool = True


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=6000)
    identity_key: str | None = Field(default=None, max_length=300)
    mode: Literal["fast", "deep", "lite"] = "fast"
    model: str | None = Field(default=None, max_length=120)  # optional installed DIT model


def _web_dir() -> Path:
    return Path(__file__).resolve().parent / "web"


def create_app() -> FastAPI:
    app = FastAPI(
        title="JARVIS Clean Research Core",
        version=__version__,
        description=(
            "Clean SENSE/Quant/Experiment/River/COLD pipeline plus bounded evidence/agents and "
            "the Chrome-first JARVIS operator workbench. Research only; transactions disabled."
        ),
        lifespan=lifespan,
    )
    web = _web_dir()
    app.mount("/workbench-assets", StaticFiles(directory=str(web)), name="workbench-assets")

    @app.get("/")
    async def root():
        return {
            "name": "JARVIS Clean Research Core",
            "version": __version__,
            "step": 4,
            "research_only": True,
            "execution_enabled": False,
            "workbench": "/workbench",
            "docs": "/docs",
            "status": "/api/status",
            "pipeline": "/api/pipeline",
            "research": "/api/research",
            "evidence": "/api/evidence",
            "attention": "/api/attention",
        }

    @app.get("/workbench", include_in_schema=False)
    async def workbench():
        return FileResponse(web / "index.html", media_type="text/html")

    @app.get("/health")
    async def health(request: Request):
        runtime = request.app.state.runtime
        return {"ok": True, "started_at": runtime.started_at, "architecture": "clean-step3+operator"}

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

    # --- Human operator layer -------------------------------------------------
    @app.get("/api/operator/overview")
    async def operator_overview(request: Request):
        return await request.app.state.runtime.operator.overview()

    @app.get("/api/operator/state")
    async def operator_state(request: Request):
        return request.app.state.runtime.operator.state()

    @app.get("/api/operator/radar")
    async def operator_radar(request: Request, limit: int = Query(80, ge=1, le=300)):
        return await request.app.state.runtime.operator.radar(limit)

    @app.get("/api/operator/dossier")
    async def operator_dossier(
        request: Request,
        identity_key: str | None = None,
        chain: str | None = None,
        contract: str | None = None,
        gmgn: bool = False,
        holders: bool = False,
    ):
        out = await request.app.state.runtime.operator.dossier(
            identity_key=identity_key, chain=chain, contract=contract,
            include_gmgn=gmgn, include_holders=holders,
        )
        if not out.get("found"):
            raise HTTPException(404, "Token is not in the canonical JARVIS universe yet")
        return out

    @app.get("/api/operator/chart")
    async def operator_chart(request: Request, identity_key: str, limit: int = Query(360, ge=20, le=1000), gmgn: bool = False):
        out = await request.app.state.runtime.operator.chart(identity_key, limit, gmgn)
        if not out.get("found"):
            raise HTTPException(404, "Token is not in the canonical JARVIS universe yet")
        return out

    @app.post("/api/operator/watch")
    async def operator_watch(request: Request, body: WatchRequest):
        return await request.app.state.runtime.operator.set_watch(body.identity_key, body.watching)

    @app.get("/api/operator/gmgn/status")
    async def gmgn_status(request: Request):
        return await request.app.state.runtime.operator.gmgn.status(force=True)

    @app.get("/api/operator/gmgn/trending")
    async def gmgn_trending(request: Request, chain: str = "sol", interval: str = "5m", limit: int = Query(30, ge=1, le=100)):
        return await request.app.state.runtime.operator.gmgn.trending(chain, interval, limit)

    @app.get("/api/operator/gmgn/trenches")
    async def gmgn_trenches(request: Request, chain: str = "sol", limit: int = Query(40, ge=1, le=100)):
        return await request.app.state.runtime.operator.gmgn.trenches(chain, limit)

    @app.get("/api/operator/gmgn/search")
    async def gmgn_search(request: Request, q: str, chain: str | None = None):
        return await request.app.state.runtime.operator.gmgn.search(q, chain)

    @app.get("/api/operator/gmgn/token")
    async def gmgn_token(request: Request, chain: str, address: str, holders: bool = False):
        try:
            return await request.app.state.runtime.operator.gmgn.token_bundle(chain, address, include_holders=holders)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/chat")
    async def chat(request: Request, body: ChatRequest):
        runtime = request.app.state.runtime
        radar = await runtime.operator.radar(10)
        identity_key = body.identity_key
        if not identity_key and radar.get("items"):
            identity_key = radar["items"][0].get("identity_key")
        await runtime.operator.append_chat("user", body.message, identity_key)

        async def stream() -> AsyncIterator[str]:
            yield json.dumps({"type": "state", "text": "JARVIS is checking canonical research state…"}) + "\n"
            task = asyncio.create_task(runtime.agents.ask(
                body.message,
                identity_key or "",
                body.mode,
                model_override=body.model if body.mode == "lite" else None,
                operator_context={
                    "radar": radar.get("items", [])[:8],
                    "pipeline": (await runtime.status()).get("pipeline", {}),
                },
            ))
            elapsed = 0
            try:
                while not task.done():
                    if await request.is_disconnected():
                        task.cancel()
                        return
                    try:
                        answer = await asyncio.wait_for(asyncio.shield(task), timeout=3.0)
                        break
                    except asyncio.TimeoutError:
                        elapsed += 3
                        yield json.dumps({"type": "heartbeat", "elapsed_s": elapsed}) + "\n"
                else:
                    answer = await task
                await runtime.operator.append_chat("jarvis", answer, identity_key)
                yield json.dumps({"type": "answer", "text": answer, "identity_key": identity_key}) + "\n"
                yield json.dumps({"type": "done"}) + "\n"
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                yield json.dumps({"type": "error", "text": f"{type(exc).__name__}: {str(exc)[:500]}"}) + "\n"

        return StreamingResponse(stream(), media_type="application/x-ndjson", headers={"X-Accel-Buffering": "no"})

    return app


app = create_app()
