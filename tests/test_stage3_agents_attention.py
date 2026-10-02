from __future__ import annotations

import asyncio
import time

import pytest

from jarvis.config import Settings
from jarvis.models import SecurityEvidence, SocialMention
from jarvis.runtime import JarvisRuntime


@pytest.fixture
def stage3_settings(tmp_path):
    return Settings(
        host="127.0.0.1", port=8768,
        data_dir=tmp_path / "data", history_dir=tmp_path / "history",
        chains=("base",), young_max_age_seconds=900, observation_fresh_seconds=180,
        tape_retention_hours=72, gecko_new_interval_seconds=9999,
        gecko_trending_interval_seconds=9999, dex_profile_interval_seconds=9999,
        dex_reconcile_interval_seconds=9999, http_timeout_seconds=3,
        archive_export_batch_rows=1000, science_min_samples=10,
        goplus_enabled=False, agents_enabled=False,
        attention_debounce_seconds=0.01, attention_cooldown_seconds=5,
    )


@pytest.mark.asyncio
async def test_attention_is_semantic_and_agents_are_noncritical(stage3_settings, young_observation):
    runtime = JarvisRuntime(stage3_settings)
    await runtime.tape.open(); await runtime.ledger.open(); await runtime.evidence.open(); await runtime.archive.open()
    processor = asyncio.create_task(runtime._processor())
    evidence = asyncio.create_task(runtime._evidence_processor())
    attention = asyncio.create_task(runtime.attention.run())
    try:
        await runtime.bus.publish(young_observation)
        await asyncio.wait_for(runtime.bus.queue.join(), timeout=3)
        await runtime.risk.ingest(SecurityEvidence(identity_key=young_observation.identity.key, provider="TEST", field="mint_authority", value=None, classification="UNKNOWN"))
        await runtime.social.ingest(SocialMention(identity_key=young_observation.identity.key, source_id="project:test", source_type="PROJECT_PUBLISHED", url="https://example.com"))
        await asyncio.sleep(0.1)
        packets = await runtime.evidence.recent_attention(20)
        assert packets
        packet = packets[0]
        assert packet.what_changed
        assert isinstance(packet.counter_evidence, list)
        assert packet.status in {"MIXED", "INCOMPLETE", "EVIDENCE_UPDATED"}
        # Agent runtime disabled: the proven market/research path still moved.
        stages = runtime.pipeline_status(runtime.metrics.snapshot(), await runtime.tape.stats(), runtime.universe.snapshot(), runtime.quant.status(), await runtime.ledger.stats())["stages"]
        assert stages["tape_accepts"] == 1
        assert stages["quant_evaluations"] == 1
        assert runtime.agents.status()["market_pipeline_dependency"] is False
    finally:
        for task in (processor, evidence, attention): task.cancel()
        await asyncio.gather(processor, evidence, attention, return_exceptions=True)
        await runtime.risk.close(); await runtime.ollama.close(); await runtime.archive.close(); await runtime.evidence.close(); await runtime.ledger.close(); await runtime.tape.close(); await runtime.sense.close()


def test_agent_role_capabilities_are_bounded(stage3_settings):
    runtime = JarvisRuntime(stage3_settings)
    status = runtime.agents.status()
    roles = status["role_capabilities"]
    assert "QUANT_SKEPTIC" in roles
    assert "risk_context" in roles["INVESTIGATOR"]
    assert "market_context" not in roles["CALLER"]
    assert status["research_only"] is True
