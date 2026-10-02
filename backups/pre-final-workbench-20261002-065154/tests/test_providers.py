from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from jarvis.metrics import Metrics
from jarvis.models import Observation
from jarvis.sense.base import ProviderLane
from jarvis.sense.dexscreener import DexScreenerProvider
from jarvis.sense.geckoterminal import GeckoTerminalProvider


def test_gecko_pool_parser_preserves_launch_time():
    now = time.time()
    pool = {
        "id": "base_0xpool",
        "attributes": {
            "address": "0xPOOL",
            "name": "ABC / WETH",
            "pool_created_at": "2026-10-02T05:00:00Z",
            "base_token_price_usd": "0.01",
            "market_cap_usd": "100000",
            "fdv_usd": "120000",
            "reserve_in_usd": "25000",
            "volume_usd": {"m5": "1000", "h1": "5000", "h24": "10000"},
            "transactions": {"m5": {"buys": 10, "sells": 5}},
            "price_change_percentage": {"m5": "2", "h1": "3", "h24": "4"},
        },
        "relationships": {"base_token": {"data": {"id": "base_0xABC"}}},
    }
    included = {"base_0xABC": {"symbol": "ABC", "name": "ABC Token"}}
    obs = GeckoTerminalProvider._parse_pool("base", pool, included, now, "new")
    assert obs is not None
    assert obs.contract == "0xabc"
    assert obs.pool == "0xpool"
    assert obs.launch_at is not None
    assert obs.buys_5m == 10


def test_dex_pair_parser_uses_pair_created_at():
    now = time.time()
    pair = {
        "pairAddress": "0xPOOL",
        "pairCreatedAt": int((now - 60) * 1000),
        "baseToken": {"address": "0xABC", "symbol": "ABC", "name": "ABC"},
        "quoteToken": {"address": "0xDEF", "symbol": "WETH", "name": "WETH"},
        "priceUsd": "0.2", "marketCap": 200000, "fdv": 250000,
        "liquidity": {"usd": 50000},
        "volume": {"m5": 1000, "h1": 5000, "h24": 20000},
        "txns": {"m5": {"buys": 12, "sells": 4}},
        "priceChange": {"m5": 1.2},
    }
    obs = DexScreenerProvider._pair_to_observation("base", "0xABC", pair, now)
    assert obs is not None
    assert obs.contract == "0xabc"
    assert obs.launch_at == pytest.approx(now - 60, abs=1)
    assert obs.liquidity == 50000


@pytest.mark.asyncio
async def test_lane_failure_does_not_cancel_other_lane():
    metrics = Metrics()
    emitted = []

    async def emit(obs):
        emitted.append(obs)

    calls = {"bad": 0, "good": 0}

    async def bad_poll():
        calls["bad"] += 1
        raise RuntimeError("simulated provider failure")

    async def good_poll():
        calls["good"] += 1
        now = time.time()
        return [Observation(observed_at=now, provider="GOOD", capability="x", chain="base",
                            contract="0xabc", pool="0xdef", launch_at=now - 30)], 1

    bad = ProviderLane("bad", "BAD", 0.05, bad_poll, emit, metrics)
    good = ProviderLane("good", "GOOD", 0.05, good_poll, emit, metrics)
    tb = asyncio.create_task(bad.run())
    tg = asyncio.create_task(good.run())
    await asyncio.sleep(0.18)
    bad.stop(); good.stop()
    await asyncio.gather(tb, tg)
    assert calls["bad"] > 0
    assert calls["good"] > 0
    assert len(emitted) > 0
    assert bad.health.errors > 0
    assert good.health.state == "LIVE"
