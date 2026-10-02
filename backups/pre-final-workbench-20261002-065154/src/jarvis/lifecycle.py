from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import Settings
from .runtime import JarvisRuntime


@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime = JarvisRuntime(Settings.from_env())
    app.state.runtime = runtime
    await runtime.start()
    try:
        yield
    finally:
        await runtime.stop()
