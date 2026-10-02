from __future__ import annotations

import asyncio

from .metrics import Metrics
from .models import Observation


class EventBus:
    """One canonical market-observation queue.

    Step 1 deliberately uses a single-consumer queue. The market processor owns the
    transition from normalized observation -> tape -> universe -> Quant, so there is
    no competing cursor or fan-out interpretation of market state.
    """

    def __init__(self, metrics: Metrics, maxsize: int = 20000) -> None:
        self.metrics = metrics
        self.queue: asyncio.Queue[Observation] = asyncio.Queue(maxsize=maxsize)

    async def publish(self, observation: Observation) -> None:
        await self.queue.put(observation)
        self.metrics.inc("event_bus_in_total")
        self.metrics.gauge("event_bus_queue_depth", self.queue.qsize())

    async def get(self) -> Observation:
        item = await self.queue.get()
        self.metrics.inc("event_bus_out_total")
        self.metrics.gauge("event_bus_queue_depth", self.queue.qsize())
        return item

    def task_done(self) -> None:
        self.queue.task_done()
