from __future__ import annotations

import asyncio
import re
import time
from typing import Any

import httpx

from .capabilities import Capability, CapabilityRegistry
from .config import Settings
from .metrics import Metrics


def _parameter_billions(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*B", str(text), flags=re.I)
    return float(m.group(1)) if m else None


class OllamaCatalog:
    """Runtime discovery of actual locally installed Ollama models."""

    def __init__(self, settings: Settings, metrics: Metrics, registry: CapabilityRegistry) -> None:
        self.settings = settings
        self.metrics = metrics
        self.registry = registry
        self.models: list[dict[str, Any]] = []
        self.last_refresh_at: float | None = None
        self.last_error: str | None = None
        self._client = httpx.AsyncClient(timeout=min(settings.http_timeout_seconds, 10.0))
        self._stop = asyncio.Event()

    async def close(self) -> None:
        self._stop.set()
        await self._client.aclose()

    async def refresh(self) -> None:
        started = time.perf_counter()
        try:
            response = await self._client.get(f"{self.settings.ollama_url}/api/tags")
            response.raise_for_status()
            body = response.json()
            rows = body.get("models") if isinstance(body, dict) else []
            parsed=[]
            for row in rows if isinstance(rows, list) else []:
                if not isinstance(row, dict):
                    continue
                name=str(row.get("name") or row.get("model") or "").strip()
                if not name:
                    continue
                details=row.get("details") if isinstance(row.get("details"), dict) else {}
                param=str(details.get("parameter_size") or "")
                parsed.append({
                    "name": name,
                    "size": row.get("size"),
                    "family": details.get("family"),
                    "families": details.get("families") or [],
                    "parameter_size": param or None,
                    "parameter_billions": _parameter_billions(param),
                    "quantization_level": details.get("quantization_level"),
                })
            self.models=parsed
            self.last_refresh_at=time.time()
            self.last_error=None
            self.metrics.gauge("ollama_models", len(parsed))
            self.registry.success("agents.ollama.local_models", (time.perf_counter()-started)*1000.0)
        except Exception as exc:
            self.last_error=f"{type(exc).__name__}: {str(exc)[:240]}"
            self.metrics.inc("ollama_discovery_errors_total")
            self.registry.failure("agents.ollama.local_models", exc)

    async def run(self) -> None:
        while not self._stop.is_set():
            await self.refresh()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.settings.ollama_refresh_seconds)
            except TimeoutError:
                pass

    def _text_models(self) -> list[dict[str, Any]]:
        out=[]
        for row in self.models:
            n=row["name"].lower()
            if any(word in n for word in ("embed", "embedding", "nomic", "bge", "vision", "llava", "-vl", ":vl")):
                continue
            out.append(row)
        return out

    def selection(self) -> dict[str, Any]:
        rows=self._text_models()
        if not rows:
            return {"fast": None, "deep": None}
        def size_key(row):
            return row.get("parameter_billions") or ((row.get("size") or 0)/1_000_000_000.0)
        ordered=sorted(rows, key=size_key)
        fast=next((row for row in ordered if (row.get("parameter_billions") or 0) >= 3), ordered[0])
        deep=ordered[-1]
        return {"fast": fast["name"], "deep": deep["name"]}

    def status(self) -> dict[str, Any]:
        return {
            "available": bool(self.models),
            "url": self.settings.ollama_url,
            "last_refresh_at": self.last_refresh_at,
            "last_error": self.last_error,
            "models": self.models,
            "selected": self.selection(),
            "names_are_runtime_discovered": True,
        }
