from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from jarvis.config import Settings
from jarvis.runtime import JarvisRuntime


@pytest.fixture
def settings(tmp_path: Path):
    return Settings(
        host="127.0.0.1", port=8768,
        data_dir=tmp_path / "data", history_dir=tmp_path / "history",
        chains=("base",), young_max_age_seconds=900, observation_fresh_seconds=180,
        tape_retention_hours=72, gecko_new_interval_seconds=9999,
        gecko_trending_interval_seconds=9999, dex_profile_interval_seconds=9999,
        dex_reconcile_interval_seconds=9999, http_timeout_seconds=3,
        archive_export_batch_rows=1000, science_min_samples=10,
    )


@pytest.mark.asyncio
async def test_single_pipeline_moves_observation_end_to_end(settings, young_observation):
    runtime = JarvisRuntime(settings)
    await runtime.tape.open()
    await runtime.ledger.open()
    await runtime.evidence.open()
    processor = asyncio.create_task(runtime._processor())
    try:
        await runtime.bus.publish(young_observation)
        await asyncio.wait_for(runtime.bus.queue.join(), timeout=3)
        status = await runtime.status()
        stages = status["pipeline"]["stages"]
        assert stages["event_bus_in"] == 1
        assert stages["event_bus_out"] == 1
        assert stages["tape_accepts"] == 1
        assert stages["universe_applies"] == 1
        assert stages["universe_eligible"] == 1
        assert stages["quant_evaluations"] == 1
        assert status["pipeline"]["broken_after"] is None
    finally:
        processor.cancel()
        await asyncio.gather(processor, return_exceptions=True)
        await runtime.sense.close()
        await runtime.evidence.close()
        await runtime.ledger.close()
        await runtime.tape.close()
