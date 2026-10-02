from __future__ import annotations

import time
from pathlib import Path

import pytest

from jarvis.experiments import ExperimentEngine
from jarvis.metrics import Metrics
from jarvis.models import Observation
from jarvis.quant import QuantEngine
from jarvis.research_ledger import ResearchLedger
from jarvis.universe import Universe


@pytest.mark.asyncio
async def test_false_to_true_opens_once_and_pins_forward_tracking(tmp_path: Path, young_observation):
    metrics = Metrics()
    path = tmp_path / "op.sqlite3"
    ledger = ResearchLedger(path, metrics)
    await ledger.open()
    try:
        universe = Universe(metrics, young_max_age_seconds=900, observation_fresh_seconds=180)
        quant = QuantEngine(universe, metrics)
        engine = ExperimentEngine(ledger, universe, metrics)

        # First observation is not yet an ACTIVE_MARKET transition because observation_count < 2.
        state = universe.apply(young_observation)
        snap = quant.evaluate(young_observation)
        assert snap is not None
        opened = await engine.evaluate(young_observation, snap, state)
        assert not [e for e in opened if e.hypothesis_id == "ACTIVE_MARKET_TRANSITION"]

        second = young_observation.model_copy(update={"event_id": "second", "observed_at": time.time() + 1})
        state = universe.apply(second)
        snap = quant.evaluate(second)
        opened = await engine.evaluate(second, snap, state)
        active = [e for e in opened if e.hypothesis_id == "ACTIVE_MARKET_TRANSITION"]
        assert len(active) == 1
        assert active[0].entry_quant["observation_count"] == 2
        assert universe.pinned_count() >= 1

        third = young_observation.model_copy(update={"event_id": "third", "observed_at": time.time() + 2})
        state = universe.apply(third)
        snap = quant.evaluate(third)
        opened_again = await engine.evaluate(third, snap, state)
        assert not [e for e in opened_again if e.hypothesis_id == "ACTIVE_MARKET_TRANSITION"]
    finally:
        await ledger.close()


@pytest.mark.asyncio
async def test_forward_marks_are_prospective_and_unique(tmp_path: Path, young_observation):
    metrics = Metrics()
    ledger = ResearchLedger(tmp_path / "op.sqlite3", metrics)
    await ledger.open()
    try:
        universe = Universe(metrics)
        quant = QuantEngine(universe, metrics)
        engine = ExperimentEngine(ledger, universe, metrics)
        universe.apply(young_observation)
        second = young_observation.model_copy(update={"event_id": "second", "observed_at": time.time() + 1})
        state = universe.apply(second)
        snap = quant.evaluate(second)
        opened = await engine.evaluate(second, snap, state)
        exp = next(e for e in opened if e.hypothesis_id == "ACTIVE_MARKET_TRANSITION")

        mark_obs = young_observation.model_copy(update={
            "event_id": "mark-5m",
            "observed_at": exp.opened_at + 301,
            "received_at": exp.opened_at + 301,
            "price": 0.011,
            "liquidity": 24000,
        })
        state = universe.apply(mark_obs)
        marks = await engine.observe(mark_obs, state)
        five = [m for m in marks if m.horizon_seconds == 300 and m.experiment_id == exp.experiment_id]
        assert len(five) == 1
        assert five[0].complete is True
        assert five[0].observed_at >= five[0].due_at

        duplicate = await engine.observe(mark_obs, state)
        assert not [m for m in duplicate if m.experiment_id == exp.experiment_id and m.horizon_seconds == 300]
    finally:
        await ledger.close()
