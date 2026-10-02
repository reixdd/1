from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jarvis.app import create_app
from jarvis.config import Settings
from jarvis.gmgn_bridge import GMGNBridge
from jarvis.metrics import Metrics
from jarvis.runtime import JarvisRuntime


def test_workbench_is_served(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("JARVIS_HISTORY_DIR", str(tmp_path / "history"))
    monkeypatch.setenv("JARVIS_GECKO_NEW_INTERVAL_SECONDS", "9999")
    monkeypatch.setenv("JARVIS_GECKO_TRENDING_INTERVAL_SECONDS", "9999")
    monkeypatch.setenv("JARVIS_DEX_PROFILE_INTERVAL_SECONDS", "9999")
    monkeypatch.setenv("JARVIS_DEX_RECONCILE_INTERVAL_SECONDS", "9999")
    app = create_app()
    with TestClient(app) as client:
        root = client.get("/").json()
        assert root["step"] == 4
        assert root["execution_enabled"] is False
        page = client.get("/workbench")
        assert page.status_code == 200
        assert "MARKET RADAR" in page.text
        assert "TRANSACTIONS DISABLED" in page.text
        assert client.get("/api/operator/radar").status_code == 200


@pytest.mark.asyncio
async def test_operator_composes_canonical_pipeline_without_owning_it(tmp_path: Path, young_observation):
    settings = Settings(
        host="127.0.0.1", port=8768,
        data_dir=tmp_path / "data", history_dir=tmp_path / "history",
        chains=("base",), young_max_age_seconds=900, observation_fresh_seconds=180,
        tape_retention_hours=72, gecko_new_interval_seconds=9999,
        gecko_trending_interval_seconds=9999, dex_profile_interval_seconds=9999,
        dex_reconcile_interval_seconds=9999, http_timeout_seconds=3,
        archive_export_batch_rows=1000, science_min_samples=10,
        agents_enabled=False,
    )
    runtime = JarvisRuntime(settings)
    await runtime.tape.open(); await runtime.ledger.open(); await runtime.evidence.open()
    processor = asyncio.create_task(runtime._processor())
    try:
        await runtime.bus.publish(young_observation)
        await asyncio.wait_for(runtime.bus.queue.join(), timeout=3)
        radar = await runtime.operator.radar()
        assert len(radar["items"]) == 1
        row = radar["items"][0]
        assert row["identity_key"] == young_observation.identity.key
        assert row["attention_score"] >= 0
        assert "buy/sell score" in radar["attention_score_note"]
        dossier = await runtime.operator.dossier(identity_key=row["identity_key"])
        assert dossier["found"] is True
        assert dossier["transactions_disabled"] is True
        chart = await runtime.operator.chart(row["identity_key"])
        assert chart["found"] is True
        await runtime.operator.set_watch(row["identity_key"], True)
        assert runtime.operator.state()["watchlist"] == [row["identity_key"]]
    finally:
        processor.cancel(); await asyncio.gather(processor, return_exceptions=True)
        await runtime.risk.close(); await runtime.ollama.close(); await runtime.archive.close()
        await runtime.evidence.close(); await runtime.ledger.close(); await runtime.tape.close(); await runtime.sense.close()


def test_gmgn_bridge_is_explicitly_read_only():
    bridge = GMGNBridge(Metrics())
    import jarvis.gmgn_bridge as module
    assert module._READ_ONLY_ROOTS == {"market", "token"}
    assert "swap" not in module._MARKET_COMMANDS
    assert "order" not in module._MARKET_COMMANDS
    assert "portfolio" not in module._READ_ONLY_ROOTS
    assert "GMGN_PRIVATE_KEY" not in Path(module.__file__).read_text(encoding="utf-8")
