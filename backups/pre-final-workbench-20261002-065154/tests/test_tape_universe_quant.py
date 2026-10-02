from __future__ import annotations

import time
from pathlib import Path

import pytest

from jarvis.metrics import Metrics
from jarvis.models import Observation
from jarvis.quant import QuantEngine
from jarvis.tape import MarketTape
from jarvis.universe import Universe


@pytest.mark.asyncio
async def test_tape_persists_and_restores(tmp_path: Path, young_observation):
    metrics = Metrics()
    tape = MarketTape(tmp_path / "op.sqlite3", metrics)
    await tape.open()
    assert await tape.append(young_observation)
    assert not await tape.append(young_observation)
    stats = await tape.stats()
    assert stats["observations"] == 1
    restored = await tape.restore_recent(3600)
    assert len(restored) == 1
    assert restored[0].event_id == young_observation.event_id
    await tape.close()


def test_universe_separates_known_from_eligible(young_observation):
    metrics = Metrics()
    universe = Universe(metrics, young_max_age_seconds=900, observation_fresh_seconds=180)
    universe.apply(young_observation)
    snap = universe.snapshot()
    assert snap["known"] == 1
    assert snap["eligible"] == 1

    old = young_observation.model_copy(update={
        "event_id": "old",
        "contract": "0xDEAD",
        "pool": "0xOLD",
        "launch_at": time.time() - 3600,
    })
    universe.apply(old)
    snap = universe.snapshot()
    assert snap["known"] == 2
    assert snap["eligible"] == 1
    assert snap["ineligible_reasons"]["too_old"] == 1


def test_quant_evaluates_eligible_observation(young_observation):
    metrics = Metrics()
    universe = Universe(metrics)
    universe.apply(young_observation)
    quant = QuantEngine(universe, metrics)
    snap = quant.evaluate(young_observation)
    assert snap is not None
    assert snap.buy_sell_imbalance == pytest.approx(0.5)
    assert snap.provider_count == 1
    assert snap.observation_count == 1
    assert quant.status()["evaluations"] == 1


def test_quant_does_not_evaluate_old_market(young_observation):
    metrics = Metrics()
    universe = Universe(metrics)
    old = young_observation.model_copy(update={"launch_at": time.time() - 5000})
    universe.apply(old)
    quant = QuantEngine(universe, metrics)
    assert quant.evaluate(old) is None
