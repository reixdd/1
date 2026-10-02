from __future__ import annotations

import asyncio
import tempfile
import time
from pathlib import Path

from .config import Settings
from .models import Observation, SecurityEvidence, SocialMention
from .runtime import JarvisRuntime


async def _main() -> int:
    with tempfile.TemporaryDirectory(prefix="jarvis-stage3-smoke-") as tmp:
        root = Path(tmp)
        settings = Settings(
            host="127.0.0.1", port=8768,
            data_dir=root / "data", history_dir=root / "history",
            chains=("base",), young_max_age_seconds=900, observation_fresh_seconds=180,
            tape_retention_hours=72, gecko_new_interval_seconds=9999,
            gecko_trending_interval_seconds=9999, dex_profile_interval_seconds=9999,
            dex_reconcile_interval_seconds=9999, http_timeout_seconds=3,
            archive_export_batch_rows=1000, science_min_samples=10,
            goplus_enabled=False, agents_enabled=False,
            attention_debounce_seconds=0.01, attention_cooldown_seconds=5,
        )
        runtime = JarvisRuntime(settings)
        await runtime.tape.open(); await runtime.ledger.open(); await runtime.evidence.open(); await runtime.archive.open()
        processor = asyncio.create_task(runtime._processor())
        evidence_task = asyncio.create_task(runtime._evidence_processor())
        attention_task = asyncio.create_task(runtime.attention.run())
        try:
            now = time.time()
            obs = Observation(
                observed_at=now,
                provider="SMOKE",
                capability="new_pool",
                chain="base",
                contract="0xabc",
                pool="0xpool",
                launch_at=now - 60,
                price=0.01,
                market_cap=100000,
                liquidity=25000,
                volume_5m=5000,
                buys_5m=20,
                sells_5m=10,
            )
            await runtime.bus.publish(obs)
            await asyncio.wait_for(runtime.bus.queue.join(), 3)
            await runtime.risk.ingest(SecurityEvidence(
                identity_key=obs.identity.key,
                provider="SMOKE_SECURITY",
                field="owner",
                value="0xowner",
            ))
            await runtime.social.ingest(SocialMention(
                identity_key=obs.identity.key,
                source_id="project:smoke",
                source_type="PROJECT_PUBLISHED",
                url="https://example.invalid/project",
            ))
            await asyncio.sleep(0.1)
            status = await runtime.status()
            packets = await runtime.evidence.recent_attention(20)
            assert status["pipeline"]["stages"]["quant_evaluations"] == 1
            assert status["stage3"]["evidence"]["security_evidence"] == 1
            assert status["stage3"]["evidence"]["social_mentions"] == 1
            assert status["stage3"]["graph"]["nodes"] >= 2
            assert packets
            assert status["stage3"]["agents"]["market_pipeline_dependency"] is False
            print("STAGE3_SMOKE_OK")
            print("quant_evaluations=1")
            print(f"attention_packets={len(packets)}")
            print("agents_required_for_core=False")
            return 0
        finally:
            for task in (processor, evidence_task, attention_task):
                task.cancel()
            await asyncio.gather(processor, evidence_task, attention_task, return_exceptions=True)
            await runtime.risk.close(); await runtime.ollama.close(); await runtime.archive.close()
            await runtime.evidence.close(); await runtime.ledger.close(); await runtime.tape.close(); await runtime.sense.close()


def main() -> None:
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
