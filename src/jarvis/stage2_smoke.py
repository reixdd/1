from __future__ import annotations

import asyncio
import json
import tempfile
import time
from pathlib import Path

from .experiments import ExperimentEngine
from .history import ColdArchive
from .metrics import Metrics
from .models import Observation
from .online import OnlineLearner
from .quant import QuantEngine
from .research_ledger import ResearchLedger
from .universe import Universe


async def run() -> dict:
    with tempfile.TemporaryDirectory(prefix="jarvis-stage2-smoke-") as td:
        root = Path(td)
        metrics = Metrics()
        ledger = ResearchLedger(root / "op.sqlite3", metrics)
        await ledger.open()
        archive = ColdArchive(root / "history", ledger, metrics, export_batch_rows=1000)
        await archive.open()
        universe = Universe(metrics)
        quant = QuantEngine(universe, metrics)
        experiments = ExperimentEngine(ledger, universe, metrics)
        online = OnlineLearner(ledger, metrics)
        await online.restore()
        try:
            if not online.available or not archive.available:
                return {
                    "ok": False,
                    "reason": "research_dependencies_missing",
                    "online": online.status(),
                    "archive": await archive.status(),
                }

            now = time.time()
            first = Observation(
                event_id="smoke-1", observed_at=now, received_at=now,
                provider="SMOKE", capability="synthetic_protocol_test",
                chain="base", contract="0xabc", pool="0xdef",
                symbol="SMOKE", launch_at=now - 60,
                price=1.0, market_cap=100000, liquidity=10000,
                volume_5m=2500, buys_5m=12, sells_5m=8,
            )
            second = first.model_copy(update={"event_id": "smoke-2", "observed_at": now + 1, "received_at": now + 1})
            universe.apply(first)
            universe.apply(second)
            snap = quant.evaluate(second)
            if snap is None:
                return {"ok": False, "reason": "quant_not_created"}
            opened = await experiments.evaluate(second, snap, universe.get(second.identity.key))
            active = [e for e in opened if e.hypothesis_id == "ACTIVE_MARKET_TRANSITION"]
            if not active:
                return {"ok": False, "reason": "experiment_not_created"}
            exp = active[0]
            pred = await online.on_experiment(exp)
            if pred is None:
                return {"ok": False, "reason": "prediction_not_created"}

            future = first.model_copy(update={
                "event_id": "smoke-15m", "observed_at": exp.opened_at + 901,
                "received_at": exp.opened_at + 901, "price": 1.01, "liquidity": 9000,
            })
            state = universe.apply(future)
            marks = await experiments.observe(future, state)
            learned = None
            for mark in marks:
                if mark.experiment_id == exp.experiment_id and mark.horizon_seconds == 900:
                    learned = await online.on_mark(exp, mark)
            if learned is None or learned.learned_at is None:
                return {"ok": False, "reason": "prediction_not_learned", "marks": [m.model_dump(mode="json") for m in marks]}

            archived = await archive.flush_once()
            await archive._maybe_export(force=True)
            archive_status = await archive.status()
            ledger_status = await ledger.stats()
            ok = (
                ledger_status["experiments"] >= 1
                and ledger_status["predictions"] >= 1
                and ledger_status["learned"] >= 1
                and archive_status["rows"] >= 1
                and archive_status["parquet_files"] >= 1
                and learned.leakage_audit == "PASS"
            )
            return {
                "ok": ok,
                "ledger": ledger_status,
                "online": online.status(),
                "archive": archive_status,
                "archived_this_run": archived,
                "leakage_audit": learned.leakage_audit,
            }
        finally:
            await archive.close()
            await ledger.close()


def main() -> None:
    result = asyncio.run(run())
    print(json.dumps(result, indent=2, default=str))
    if not result.get("ok"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
