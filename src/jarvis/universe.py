from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from typing import Any

from .metrics import Metrics
from .models import Observation


@dataclass(slots=True)
class MarketState:
    identity_key: str
    chain: str
    contract: str
    pool: str | None
    symbol: str | None = None
    name: str | None = None
    launch_at: float | None = None
    last_observed_at: float = 0.0
    last_received_at: float = 0.0
    latest: dict[str, Any] = field(default_factory=dict)
    providers: dict[str, dict[str, Any]] = field(default_factory=dict)
    observation_count: int = 0

    def as_dict(self, now: float | None = None) -> dict[str, Any]:
        now = time.time() if now is None else now
        return {
            "identity_key": self.identity_key,
            "chain": self.chain,
            "contract": self.contract,
            "pool": self.pool,
            "symbol": self.symbol,
            "name": self.name,
            "launch_at": self.launch_at,
            "age_seconds": (now - self.launch_at) if self.launch_at else None,
            "last_observed_at": self.last_observed_at,
            "observation_age_seconds": now - self.last_observed_at if self.last_observed_at else None,
            "provider_count": len(self.providers),
            "providers": sorted(self.providers),
            "observation_count": self.observation_count,
            **self.latest,
        }


class Universe:
    """Provider-neutral current market population.

    Universe answers "what currently exists and is young/fresh?" It does not decide
    whether a market is a good research hypothesis.
    """

    def __init__(self, metrics: Metrics, young_max_age_seconds: float = 900.0,
                 observation_fresh_seconds: float = 180.0) -> None:
        self.metrics = metrics
        self.young_max_age_seconds = young_max_age_seconds
        self.observation_fresh_seconds = observation_fresh_seconds
        self._states: dict[str, MarketState] = {}
        self._reasons: dict[str, int] = {}
        self._pins: dict[str, float] = {}

    def apply(self, obs: Observation, *, restored: bool = False) -> MarketState:
        key = obs.identity.key
        state = self._states.get(key)
        if state is None:
            state = MarketState(key, obs.chain, obs.contract, obs.pool)
            self._states[key] = state
        payload = obs.model_dump(mode="python")
        state.symbol = obs.symbol or state.symbol
        state.name = obs.name or state.name
        state.launch_at = obs.launch_at or state.launch_at
        state.last_observed_at = max(state.last_observed_at, obs.observed_at)
        state.last_received_at = max(state.last_received_at, obs.received_at)
        state.observation_count += 1
        state.providers[obs.provider] = payload
        # The newest observation is the display baseline, but provider disagreement is retained separately.
        if obs.observed_at >= float(state.latest.get("observed_at") or 0):
            for field in (
                "observed_at", "price", "market_cap", "fdv", "liquidity", "volume_5m", "volume_1h",
                "volume_24h", "buys_5m", "sells_5m", "price_change_5m_pct", "price_change_1h_pct",
                "price_change_24h_pct", "provider", "capability", "event_type",
            ):
                value = payload.get(field)
                if value is not None:
                    state.latest[field] = value
        if not restored:
            self.metrics.inc("universe_apply_total")
        self._update_metrics()
        return state

    def _eligible(self, state: MarketState, now: float) -> tuple[bool, str]:
        if state.launch_at is None:
            return False, "missing_launch_at"
        age = now - state.launch_at
        if age < -30:
            return False, "launch_in_future"
        if age > self.young_max_age_seconds:
            return False, "too_old"
        if now - state.last_observed_at > self.observation_fresh_seconds:
            return False, "stale_observation"
        return True, "eligible"

    def eligible(self, now: float | None = None) -> list[MarketState]:
        now = time.time() if now is None else now
        out = []
        reasons: dict[str, int] = {}
        for state in self._states.values():
            good, reason = self._eligible(state, now)
            reasons[reason] = reasons.get(reason, 0) + 1
            if good:
                out.append(state)
        self._reasons = reasons
        self.metrics.gauge("universe_size", len(out))
        self.metrics.gauge("universe_known_total", len(self._states))
        return out

    def _update_metrics(self) -> None:
        self.eligible()

    def is_eligible(self, identity_key: str, now: float | None = None) -> bool:
        state = self._states.get(identity_key)
        if state is None:
            return False
        return self._eligible(state, time.time() if now is None else now)[0]

    def get(self, identity_key: str) -> MarketState | None:
        return self._states.get(identity_key)

    def find(self, chain: str, contract: str) -> MarketState | None:
        """Resolve the freshest known canonical market for a chain+contract.

        Pools remain distinct identities internally; this convenience method is read-only
        and is used by the operator layer when a human pastes a contract address.
        """
        chain = str(chain or "").strip().lower()
        contract_raw = str(contract or "").strip()
        contract_cmp = contract_raw.lower() if chain in {"eth", "base", "bsc", "arbitrum", "optimism", "polygon"} else contract_raw
        matches = [
            state for state in self._states.values()
            if state.chain == chain and state.contract == contract_cmp
        ]
        return max(matches, key=lambda state: state.last_observed_at) if matches else None

    def known(self, limit: int = 2000) -> list[MarketState]:
        """Read-only view of known markets, newest observations first."""
        return sorted(self._states.values(), key=lambda state: state.last_observed_at, reverse=True)[:max(1, min(10000, int(limit)))]

    def pin(self, identity_key: str, until: float) -> None:
        """Keep a market on the provider reconciliation list for prospective research.

        Pinning does not make the market eligible for HOT/Quant after it ages out. It
        only keeps future observations flowing so already-open experiments can mature.
        """
        current = self._pins.get(identity_key, 0.0)
        if until > current:
            self._pins[identity_key] = float(until)

    def pinned_count(self, now: float | None = None) -> int:
        now = time.time() if now is None else now
        self._pins = {key: until for key, until in self._pins.items() if until > now}
        return len(self._pins)

    def snapshot(self, limit: int = 500) -> dict[str, Any]:
        now = time.time()
        eligible = self.eligible(now)
        eligible.sort(key=lambda s: (s.launch_at or 0), reverse=True)
        return {
            "at": now,
            "known": len(self._states),
            "eligible": len(eligible),
            "criteria": {
                "young_max_age_seconds": self.young_max_age_seconds,
                "observation_fresh_seconds": self.observation_fresh_seconds,
            },
            "ineligible_reasons": dict(self._reasons),
            "items": [s.as_dict(now) for s in eligible[: max(1, min(2000, limit))]],
        }

    def targets(self, max_age_seconds: float = 3600.0, limit: int = 1000) -> list[tuple[str, str]]:
        now = time.time()
        self._pins = {key: until for key, until in self._pins.items() if until > now}
        out: list[tuple[str, str]] = []
        seen = set()
        for state in sorted(self._states.values(), key=lambda s: s.last_observed_at, reverse=True):
            naturally_recent = bool(state.launch_at and now - state.launch_at <= max_age_seconds)
            pinned = state.identity_key in self._pins
            if not naturally_recent and not pinned:
                continue
            key = (state.chain, state.contract)
            if key in seen:
                continue
            seen.add(key)
            out.append(key)
            if len(out) >= limit:
                break
        self.metrics.gauge("research_tracking_targets", len(self._pins))
        return out

    @staticmethod
    def disagreement(state: MarketState) -> float | None:
        prices = []
        for payload in state.providers.values():
            value = payload.get("price")
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            if value > 0:
                prices.append(value)
        if len(prices) < 2:
            return None
        med = statistics.median(prices)
        return (max(prices) - min(prices)) / med if med else None
