from __future__ import annotations

import httpx

from ..bus import EventBus
from ..config import Settings
from ..metrics import Metrics
from ..universe import Universe
from .base import ProviderLane
from .dexscreener import DexScreenerProvider
from .geckoterminal import GeckoTerminalProvider


class SenseManager:
    """Exactly one owner of external market-data provider polling."""

    def __init__(self, settings: Settings, bus: EventBus, universe: Universe, metrics: Metrics) -> None:
        self.settings = settings
        self.bus = bus
        self.universe = universe
        self.metrics = metrics
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.http_timeout_seconds),
            headers={"User-Agent": "JARVIS-Research-Core/0.1 (+read-only research)"},
            follow_redirects=True,
        )
        self.gecko = GeckoTerminalProvider(self.client, settings.chains)
        self.dex = DexScreenerProvider(self.client, settings.chains, self.universe.targets)
        self.lanes = [
            ProviderLane(
                "gecko_new", "GeckoTerminal", settings.gecko_new_interval_seconds,
                lambda: self.gecko.discover("new"), bus.publish, metrics,
                budget_max_calls=30, initial_delay_s=0.1,
            ),
            ProviderLane(
                "gecko_trending", "GeckoTerminal", settings.gecko_trending_interval_seconds,
                lambda: self.gecko.discover("trending"), bus.publish, metrics,
                budget_max_calls=30, initial_delay_s=5.0,
            ),
            ProviderLane(
                "dex_profiles", "DEX Screener", settings.dex_profile_interval_seconds,
                self.dex.profiles, bus.publish, metrics,
                budget_max_calls=60, initial_delay_s=2.0,
            ),
            ProviderLane(
                "dex_reconcile", "DEX Screener", settings.dex_reconcile_interval_seconds,
                self.dex.reconcile, bus.publish, metrics,
                budget_max_calls=300, initial_delay_s=8.0,
            ),
        ]

    async def close(self) -> None:
        for lane in self.lanes:
            lane.stop()
        await self.client.aclose()

    def status(self) -> dict:
        return {
            "owner": "SenseManager",
            "research_only": True,
            "providers": [lane.health.snapshot() for lane in self.lanes],
            "gmgn": {
                "state": "NOT_CONNECTED",
                "role": "optional depth/enrichment",
                "detail": "Clean Step 1 intentionally does not import the legacy GMGN runtime. A read-only bridge is a later bounded capability.",
            },
        }
