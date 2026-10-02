from __future__ import annotations

import math
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field, field_validator

EVM_CHAINS = {"eth", "base", "bsc", "arbitrum", "optimism", "polygon"}


def canonical_address(chain: str, value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text.lower() if str(chain).lower() in EVM_CHAINS else text


def finite(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


class MarketIdentity(BaseModel):
    chain: str
    contract: str
    pool: str | None = None

    @field_validator("chain")
    @classmethod
    def _chain(cls, value: str) -> str:
        value = str(value).strip().lower()
        if not value:
            raise ValueError("chain is required")
        return value

    @field_validator("contract")
    @classmethod
    def _contract(cls, value: str, info):
        chain = str(info.data.get("chain") or "").lower()
        value = canonical_address(chain, value)
        if not value:
            raise ValueError("contract is required")
        return value

    @field_validator("pool")
    @classmethod
    def _pool(cls, value: str | None, info):
        return canonical_address(str(info.data.get("chain") or "").lower(), value)

    @property
    def key(self) -> str:
        return f"{self.chain}:{self.contract}:{self.pool or '-'}"


class Observation(BaseModel):
    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    observed_at: float
    received_at: float = Field(default_factory=time.time)
    provider: str
    capability: str
    chain: str
    contract: str
    pool: str | None = None
    source_identity: str | None = None
    event_type: str = "market_observation"

    symbol: str | None = None
    name: str | None = None
    launch_at: float | None = None
    price: float | None = None
    market_cap: float | None = None
    fdv: float | None = None
    liquidity: float | None = None
    volume_5m: float | None = None
    volume_1h: float | None = None
    volume_24h: float | None = None
    buys_5m: float | None = None
    sells_5m: float | None = None
    price_change_5m_pct: float | None = None
    price_change_1h_pct: float | None = None
    price_change_24h_pct: float | None = None

    provenance: dict[str, Any] = Field(default_factory=dict)
    quality_flags: list[str] = Field(default_factory=list)

    @field_validator("chain")
    @classmethod
    def _chain(cls, value: str) -> str:
        value = str(value).strip().lower()
        if not value:
            raise ValueError("chain is required")
        return value

    @field_validator("contract")
    @classmethod
    def _contract(cls, value: str, info):
        out = canonical_address(str(info.data.get("chain") or ""), value)
        if not out:
            raise ValueError("contract is required")
        return out

    @field_validator("pool")
    @classmethod
    def _pool(cls, value: str | None, info):
        return canonical_address(str(info.data.get("chain") or ""), value)

    @field_validator(
        "observed_at", "received_at", "launch_at", "price", "market_cap", "fdv", "liquidity",
        "volume_5m", "volume_1h", "volume_24h", "buys_5m", "sells_5m",
        "price_change_5m_pct", "price_change_1h_pct", "price_change_24h_pct",
        mode="before",
    )
    @classmethod
    def _numbers(cls, value):
        return finite(value)

    @property
    def identity(self) -> MarketIdentity:
        return MarketIdentity(chain=self.chain, contract=self.contract, pool=self.pool)


class QuantSnapshot(BaseModel):
    snapshot_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    event_id: str
    identity_key: str
    evaluated_at: float = Field(default_factory=time.time)
    age_seconds: float | None = None
    market_cap: float | None = None
    liquidity: float | None = None
    volume_5m: float | None = None
    tx_buy_count: float | None = None
    tx_sell_count: float | None = None
    buy_sell_imbalance: float | None = None
    rank: int | None = None
    rank_velocity_per_min: float | None = None
    provider_count: int = 0
    provider_disagreement: float | None = None
    observation_count: int = 0

class ExperimentRecord(BaseModel):
    experiment_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    hypothesis_id: str
    identity_key: str
    source_event_id: str
    opened_at: float = Field(default_factory=time.time)
    entry_price: float | None = None
    entry_market_cap: float | None = None
    entry_liquidity: float | None = None
    entry_quant: dict[str, Any] = Field(default_factory=dict)
    entry_market: dict[str, Any] = Field(default_factory=dict)
    trigger_version: str = "v1"
    control: bool = False
    status: str = "OPEN"
    max_return_pct: float | None = None
    min_return_pct: float | None = None


class ForwardMark(BaseModel):
    mark_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    experiment_id: str
    identity_key: str
    horizon_seconds: int
    due_at: float
    observed_at: float
    price: float | None = None
    market_cap: float | None = None
    liquidity: float | None = None
    return_pct: float | None = None
    mfe_pct: float | None = None
    mae_pct: float | None = None
    complete: bool = False
    completeness_reason: str | None = None


class OnlinePrediction(BaseModel):
    prediction_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    experiment_id: str
    identity_key: str
    model_key: str
    created_at: float = Field(default_factory=time.time)
    features_frozen_at: float
    features: dict[str, float] = Field(default_factory=dict)
    predicted_probability: float | None = None
    label_due_at: float
    label_name: str = "liquidity_retention_15m"
    label: bool | None = None
    label_observed_at: float | None = None
    score: float | None = None
    learned_at: float | None = None
    leakage_audit: str = "PENDING"


class SecurityEvidence(BaseModel):
    evidence_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    identity_key: str
    provider: str
    observed_at: float = Field(default_factory=time.time)
    field: str
    value: Any = None
    classification: str = "CLAIM"
    confidence: str = "PROVIDER_REPORTED"
    source_url: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)


class GraphEdgeRecord(BaseModel):
    edge_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    source_node: str
    target_node: str
    relation: str
    provider: str
    first_seen_at: float = Field(default_factory=time.time)
    last_seen_at: float = Field(default_factory=time.time)
    observations: int = 1
    weight: float = 1.0
    identity_key: str | None = None
    evidence_id: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class SocialMention(BaseModel):
    mention_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    identity_key: str
    source_id: str
    source_type: str
    observed_at: float = Field(default_factory=time.time)
    text: str = ""
    url: str | None = None
    platform: str | None = None
    independent: bool = False
    provenance: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_type")
    @classmethod
    def _source_type(cls, value: str) -> str:
        value = str(value).strip().upper()
        allowed = {"PROJECT_PUBLISHED", "INDEPENDENT_MENTION", "CALLER_MENTION", "RECURRING_SOURCE"}
        if value not in allowed:
            raise ValueError(f"source_type must be one of {sorted(allowed)}")
        return value


class MemoryItem(BaseModel):
    memory_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    identity_key: str | None = None
    classification: str
    content: str
    observed_at: float = Field(default_factory=time.time)
    source: str
    confidence: str = "UNKNOWN"
    related_ids: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)

    @field_validator("classification")
    @classmethod
    def _classification(cls, value: str) -> str:
        value = str(value).strip().upper()
        allowed = {"FACT", "OBSERVATION", "HYPOTHESIS", "UNVERIFIED_CLAIM", "AGENT_CONCLUSION"}
        if value not in allowed:
            raise ValueError(f"classification must be one of {sorted(allowed)}")
        return value


class AttentionPacket(BaseModel):
    packet_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    identity_key: str
    created_at: float = Field(default_factory=time.time)
    trigger_reasons: list[str] = Field(default_factory=list)
    what_changed: list[str] = Field(default_factory=list)
    why_it_matters_for_research: list[str] = Field(default_factory=list)
    counter_evidence: list[str] = Field(default_factory=list)
    historical_context: dict[str, Any] = Field(default_factory=dict)
    base_rate: dict[str, Any] = Field(default_factory=dict)
    unknowns: list[str] = Field(default_factory=list)
    status: str = "NEEDS_RESEARCH"
    evidence_ids: list[str] = Field(default_factory=list)
    agent_run_ids: list[str] = Field(default_factory=list)


class AgentRunRecord(BaseModel):
    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    packet_id: str
    identity_key: str
    agent_name: str
    started_at: float = Field(default_factory=time.time)
    finished_at: float | None = None
    model: str | None = None
    status: str = "STARTED"
    output: str | None = None
    latency_ms: float | None = None
    error: str | None = None
