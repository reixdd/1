from __future__ import annotations

import time
from pathlib import Path

import pytest

pytest.importorskip("river")

from jarvis.metrics import Metrics
from jarvis.models import ExperimentRecord, ForwardMark
from jarvis.online import OnlineLearner
from jarvis.research_ledger import ResearchLedger


@pytest.mark.asyncio
async def test_river_predict_freeze_future_label_score_learn(tmp_path: Path):
    metrics = Metrics()
    ledger = ResearchLedger(tmp_path / "op.sqlite3", metrics)
    await ledger.open()
    try:
        learner = OnlineLearner(ledger, metrics)
        assert learner.available
        opened = time.time()
        exp = ExperimentRecord(
            hypothesis_id="TEST",
            identity_key="base:0xabc:0xpool",
            source_event_id="e0",
            opened_at=opened,
            entry_price=1.0,
            entry_market_cap=100000,
            entry_liquidity=10000,
            entry_quant={
                "age_seconds": 60,
                "market_cap": 100000,
                "liquidity": 10000,
                "volume_5m": 3000,
                "buy_sell_imbalance": 0.2,
                "rank": 4,
                "rank_velocity_per_min": 1.0,
                "provider_count": 2,
                "provider_disagreement": 0.02,
                "observation_count": 3,
            },
        )
        assert await ledger.insert_experiment(exp)
        pred = await learner.on_experiment(exp)
        assert pred is not None
        assert pred.learned_at is None
        frozen = dict(pred.features)

        mark = ForwardMark(
            experiment_id=exp.experiment_id,
            identity_key=exp.identity_key,
            horizon_seconds=900,
            due_at=opened + 900,
            observed_at=opened + 901,
            price=1.01,
            market_cap=101000,
            liquidity=9000,
            complete=True,
        )
        learned = await learner.on_mark(exp, mark)
        assert learned is not None
        assert learned.features == frozen
        assert learned.label is True
        assert learned.leakage_audit == "PASS"
        assert learned.learned_at is not None
        assert (await ledger.stats())["learned"] == 1
    finally:
        await ledger.close()
