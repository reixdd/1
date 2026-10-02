from __future__ import annotations

import time
import pytest

from jarvis.models import Observation


@pytest.fixture
def young_observation():
    now = time.time()
    return Observation(
        observed_at=now,
        provider="TEST",
        capability="new_pool",
        chain="base",
        contract="0xABCDEF",
        pool="0xPOOL123",
        symbol="TEST",
        name="Test Token",
        launch_at=now - 60,
        price=0.01,
        market_cap=100000,
        liquidity=25000,
        volume_5m=5000,
        buys_5m=30,
        sells_5m=10,
    )
