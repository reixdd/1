from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass
from typing import Callable

from .metrics import Metrics
from .models import ExperimentRecord, ForwardMark, Observation, QuantSnapshot
from .research_ledger import ResearchLedger
from .universe import MarketState, Universe

HORIZONS = (300, 900, 1800, 3600, 10800, 21600, 86400)


@dataclass(frozen=True, slots=True)
class Hypothesis:
    hypothesis_id: str
    version: str
    predicate: Callable[[QuantSnapshot, MarketState], bool]
    control: bool = False


class ExperimentEngine:
    """Prospective-only research experiment owner.

    Experiments open only on false -> true transitions. The engine never reconstructs
    an entry after seeing the future and it never uses a pretend bankroll to gate
    scientific sampling.
    """

    def __init__(self, ledger: ResearchLedger, universe: Universe, metrics: Metrics) -> None:
        self.ledger = ledger
        self.universe = universe
        self.metrics = metrics
        self.hypotheses = (
            Hypothesis("ACTIVE_MARKET_TRANSITION", "1", self._active_market),
            Hypothesis("MULTISOURCE_TRANSITION", "1", self._multisource),
            Hypothesis("RANDOM_CONTROL", "1", self._random_control, control=True),
        )

    @staticmethod
    def _finite(value) -> float | None:
        try:
            out = float(value)
            return out if math.isfinite(out) else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def _active_market(cls, snap: QuantSnapshot, state: MarketState) -> bool:
        # Neutral research cohort: observable activity, not a buy/sell recommendation.
        volume = cls._finite(snap.volume_5m) or 0.0
        liquidity = cls._finite(snap.liquidity) or 0.0
        buys = cls._finite(snap.tx_buy_count) or 0.0
        sells = cls._finite(snap.tx_sell_count) or 0.0
        return state.observation_count >= 2 and liquidity > 0 and (volume > 0 or buys + sells >= 4)

    @staticmethod
    def _multisource(snap: QuantSnapshot, state: MarketState) -> bool:
        return snap.provider_count >= 2 and state.observation_count >= 2

    @staticmethod
    def _random_control(snap: QuantSnapshot, state: MarketState) -> bool:
        # Stable 5% prospective control sample based only on identity, not outcomes.
        digest = hashlib.blake2b(state.identity_key.encode("utf-8"), digest_size=8).digest()
        return int.from_bytes(digest, "big") % 20 == 0

    async def restore_tracking(self) -> None:
        now = time.time()
        for exp in await self.ledger.open_experiments():
            self.universe.pin(exp.identity_key, max(now + 60.0, exp.opened_at + max(HORIZONS) + 300.0))

    async def evaluate(self, obs: Observation, snap: QuantSnapshot, state: MarketState) -> list[ExperimentRecord]:
        opened: list[ExperimentRecord] = []
        for hypothesis in self.hypotheses:
            active = bool(hypothesis.predicate(snap, state))
            previous = await self.ledger.get_condition(hypothesis.hypothesis_id, state.identity_key)
            if active and not previous:
                record = ExperimentRecord(
                    hypothesis_id=hypothesis.hypothesis_id,
                    identity_key=state.identity_key,
                    source_event_id=obs.event_id,
                    opened_at=snap.evaluated_at,
                    entry_price=self._finite(state.latest.get("price")),
                    entry_market_cap=self._finite(state.latest.get("market_cap")),
                    entry_liquidity=self._finite(state.latest.get("liquidity")),
                    entry_quant=snap.model_dump(mode="json"),
                    entry_market=state.as_dict(snap.evaluated_at),
                    trigger_version=hypothesis.version,
                    control=hypothesis.control,
                )
                if await self.ledger.insert_experiment(record):
                    self.universe.pin(
                        state.identity_key,
                        record.opened_at + max(HORIZONS) + 300.0,
                    )
                    opened.append(record)
            await self.ledger.set_condition(
                hypothesis.hypothesis_id,
                state.identity_key,
                active,
                obs.event_id,
                snap.evaluated_at,
            )
        return opened

    async def observe(self, obs: Observation, state: MarketState) -> list[ForwardMark]:
        now = max(time.time(), obs.observed_at)
        price = self._finite(state.latest.get("price"))
        market_cap = self._finite(state.latest.get("market_cap"))
        liquidity = self._finite(state.latest.get("liquidity"))
        marks_created: list[ForwardMark] = []
        for exp in await self.ledger.open_experiments(state.identity_key):
            ret = None
            if price is not None and exp.entry_price not in (None, 0):
                ret = (price / float(exp.entry_price) - 1.0) * 100.0
                updated = await self.ledger.update_excursion(exp.experiment_id, ret)
                if updated is not None:
                    exp = updated
            existing = {mark.horizon_seconds for mark in await self.ledger.marks_for(exp.experiment_id)}
            for horizon in HORIZONS:
                if horizon in existing or now < exp.opened_at + horizon:
                    continue
                complete = price is not None
                mark = ForwardMark(
                    experiment_id=exp.experiment_id,
                    identity_key=exp.identity_key,
                    horizon_seconds=horizon,
                    due_at=exp.opened_at + horizon,
                    observed_at=obs.observed_at,
                    price=price,
                    market_cap=market_cap,
                    liquidity=liquidity,
                    return_pct=ret,
                    mfe_pct=exp.max_return_pct,
                    mae_pct=exp.min_return_pct,
                    complete=complete,
                    completeness_reason=None if complete else "price_unavailable_at_forward_observation",
                )
                if await self.ledger.insert_mark(mark):
                    marks_created.append(mark)
        return marks_created

    async def status(self) -> dict:
        stats = await self.ledger.stats()
        return {
            **stats,
            "hypotheses": [
                {"id": h.hypothesis_id, "version": h.version, "control": h.control}
                for h in self.hypotheses
            ],
            "horizons_seconds": list(HORIZONS),
            "prospective_only": True,
            "bankroll_gated": False,
        }
