from __future__ import annotations

import time
from collections import deque
from typing import Any

import numpy as np

from .metrics import Metrics
from .models import Observation, QuantSnapshot
from .universe import MarketState, Universe


class QuantEngine:
    """Deterministic HOT/Quant feature engine. No model or LLM calls live here."""

    def __init__(self, universe: Universe, metrics: Metrics, recent_limit: int = 5000) -> None:
        self.universe = universe
        self.metrics = metrics
        self._recent: deque[QuantSnapshot] = deque(maxlen=recent_limit)
        self._last_rank: dict[str, tuple[int, float]] = {}

    def evaluate(self, obs: Observation) -> QuantSnapshot | None:
        started = time.perf_counter()
        state = self.universe.get(obs.identity.key)
        if state is None or not self.universe.is_eligible(obs.identity.key):
            return None
        now = time.time()
        cohort = self.universe.eligible(now)
        rank = self._rank(state, cohort)
        rank_velocity = None
        prior = self._last_rank.get(state.identity_key)
        if rank is not None and prior is not None:
            prior_rank, prior_at = prior
            minutes = (now - prior_at) / 60.0
            if minutes > 1e-6:
                # Positive means rank improved (e.g. 20 -> 10).
                rank_velocity = (prior_rank - rank) / minutes
        if rank is not None:
            self._last_rank[state.identity_key] = (rank, now)

        latest = state.latest
        buys = self._num(latest.get("buys_5m"))
        sells = self._num(latest.get("sells_5m"))
        denom = (buys or 0.0) + (sells or 0.0)
        imbalance = ((buys or 0.0) - (sells or 0.0)) / denom if denom > 0 else None
        snap = QuantSnapshot(
            event_id=obs.event_id,
            identity_key=state.identity_key,
            evaluated_at=now,
            age_seconds=(now - state.launch_at) if state.launch_at else None,
            market_cap=self._num(latest.get("market_cap")),
            liquidity=self._num(latest.get("liquidity")),
            volume_5m=self._num(latest.get("volume_5m")),
            tx_buy_count=buys,
            tx_sell_count=sells,
            buy_sell_imbalance=imbalance,
            rank=rank,
            rank_velocity_per_min=rank_velocity,
            provider_count=len(state.providers),
            provider_disagreement=self.universe.disagreement(state),
            observation_count=state.observation_count,
        )
        self._recent.append(snap)
        self.metrics.inc("quant_eval_total")
        self.metrics.observe("quant_latency_ms", (time.perf_counter() - started) * 1000.0)
        self.metrics.gauge("quant_eval_per_second", self.metrics.rate("quant_eval_total", 60.0))
        return snap

    @staticmethod
    def _num(value: Any) -> float | None:
        try:
            out = float(value)
            return out if np.isfinite(out) else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _rank(state: MarketState, cohort: list[MarketState]) -> int | None:
        scored = []
        for item in cohort:
            try:
                mc = float(item.latest.get("market_cap"))
            except (TypeError, ValueError):
                continue
            if np.isfinite(mc) and mc >= 0:
                scored.append((item.identity_key, mc))
        if not scored or state.identity_key not in {k for k, _ in scored}:
            return None
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return next(i for i, (key, _) in enumerate(scored, 1) if key == state.identity_key)

    def status(self) -> dict[str, Any]:
        metrics = self.metrics.snapshot()
        hist = metrics["histograms"].get("quant_latency_ms", {})
        return {
            "evaluations": int(metrics["counters"].get("quant_eval_total", 0)),
            "eval_per_second_60s": metrics["rates_per_second_60s"].get("quant_eval_total", 0.0),
            "latency_ms": hist,
            "recent_count": len(self._recent),
            "deterministic": True,
            "model_free": True,
        }

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        items = list(self._recent)[-max(1, min(1000, int(limit))):]
        return [item.model_dump(mode="json") for item in reversed(items)]
