from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
import time
from dataclasses import replace
from pathlib import Path

from .config import Settings
from .runtime import JarvisRuntime


async def run(seconds: float) -> dict:
    base = Settings.from_env()
    with tempfile.TemporaryDirectory(prefix="jarvis-smoke-") as td:
        settings = replace(base, data_dir=Path(td) / "data", history_dir=Path(td) / "history")
        runtime = JarvisRuntime(settings)
        await runtime.start()
        try:
            await asyncio.sleep(max(5.0, seconds))
            status = await runtime.status()
            stages = status["pipeline"]["stages"]
            return {
                "ok": stages["provider_observations"] > 0 and stages["tape_accepts"] > 0,
                "quant_expected": stages["universe_eligible"] > 0,
                "quant_live": stages["quant_evaluations"] > 0,
                "pipeline": status["pipeline"],
                "providers": status["sense"]["providers"],
                "universe": status["universe"],
                "quant": status["quant"],
            }
        finally:
            await runtime.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Live provider/pipeline smoke test")
    parser.add_argument("--seconds", type=float, default=75.0)
    args = parser.parse_args()
    result = asyncio.run(run(args.seconds))
    print(json.dumps(result, indent=2, default=str))
    if not result["ok"] or (result["quant_expected"] and not result["quant_live"]):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
