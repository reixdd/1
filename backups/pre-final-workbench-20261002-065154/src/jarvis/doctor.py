from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import sys

from .config import Settings


def report() -> dict:
    settings = Settings.from_env()
    packages = {}
    for name in ("fastapi", "uvicorn", "httpx", "pydantic", "numpy", "river", "duckdb", "polars", "pyarrow", "optuna", "networkx", "openai-agents"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {
        "python": sys.version,
        "executable": sys.executable,
        "cwd": os.getcwd(),
        "platform": platform.platform(),
        "jarvis_import": __package__.split(".")[0],
        "sqlite_path": str(settings.sqlite_path),
        "chains": settings.chains,
        "packages": packages,
        "research_only": True,
    }


def main() -> None:
    print(json.dumps(report(), indent=2, default=str))


if __name__ == "__main__":
    main()
