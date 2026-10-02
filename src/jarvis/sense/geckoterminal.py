from __future__ import annotations

from datetime import datetime
import time
from typing import Any

import httpx

from ..models import Observation, finite

NETWORKS = {
    "sol": "solana",
    "eth": "eth",
    "base": "base",
    "bsc": "bsc",
}


def _epoch(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def _rel_address(chain: str, relationship: dict[str, Any] | None) -> str | None:
    raw = (((relationship or {}).get("data") or {}).get("id") or "")
    prefix = NETWORKS[chain] + "_"
    if raw.startswith(prefix):
        return raw[len(prefix):]
    return raw.split("_", 1)[1] if "_" in raw else (raw or None)


class GeckoTerminalProvider:
    name = "GeckoTerminal"
    base_url = "https://api.geckoterminal.com/api/v2"

    def __init__(self, client: httpx.AsyncClient, chains: tuple[str, ...]) -> None:
        self.client = client
        self.chains = tuple(chain for chain in chains if chain in NETWORKS)

    async def discover(self, kind: str) -> tuple[list[Observation], int]:
        if kind not in {"new", "trending"}:
            raise ValueError("kind must be new or trending")
        segment = "new_pools" if kind == "new" else "trending_pools"
        observations: list[Observation] = []
        calls = 0
        for chain in self.chains:
            network = NETWORKS[chain]
            url = f"{self.base_url}/networks/{network}/{segment}"
            response = await self.client.get(url, params={"include": "base_token", "page": 1})
            calls += 1
            response.raise_for_status()
            observed_at = time.time()
            body = response.json()
            included = {
                item.get("id"): item.get("attributes") or {}
                for item in (body.get("included") or []) if isinstance(item, dict)
            }
            for pool in body.get("data") or []:
                obs = self._parse_pool(chain, pool, included, observed_at, kind)
                if obs is not None:
                    observations.append(obs)
        return observations, calls

    @staticmethod
    def _parse_pool(chain: str, pool: dict[str, Any], included: dict[str, dict],
                    observed_at: float, kind: str) -> Observation | None:
        attrs = pool.get("attributes") or {}
        rel = pool.get("relationships") or {}
        contract = _rel_address(chain, rel.get("base_token") or {})
        if not contract:
            return None
        token_id = (((rel.get("base_token") or {}).get("data") or {}).get("id") or "")
        meta = included.get(token_id, {})
        tx = attrs.get("transactions") or {}
        m5 = tx.get("m5") or {}
        volume = attrs.get("volume_usd") or {}
        changes = attrs.get("price_change_percentage") or {}
        pool_addr = attrs.get("address") or (pool.get("id") or "").split("_", 1)[-1] or None
        name = meta.get("name") or str(attrs.get("name") or "").split("/")[0].strip() or None
        symbol = meta.get("symbol") or name
        return Observation(
            observed_at=observed_at,
            provider="GeckoTerminal",
            capability=f"{kind}_pool_discovery",
            chain=chain,
            contract=contract,
            pool=pool_addr,
            source_identity=token_id or None,
            event_type="pool_discovery",
            symbol=symbol,
            name=name,
            launch_at=_epoch(attrs.get("pool_created_at")),
            price=finite(attrs.get("base_token_price_usd")),
            market_cap=finite(attrs.get("market_cap_usd")),
            fdv=finite(attrs.get("fdv_usd")),
            liquidity=finite(attrs.get("reserve_in_usd")),
            volume_5m=finite(volume.get("m5")),
            volume_1h=finite(volume.get("h1")),
            volume_24h=finite(volume.get("h24")),
            buys_5m=finite(m5.get("buys")),
            sells_5m=finite(m5.get("sells")),
            price_change_5m_pct=finite(changes.get("m5")),
            price_change_1h_pct=finite(changes.get("h1")),
            price_change_24h_pct=finite(changes.get("h24")),
            provenance={
                "endpoint_family": "GeckoTerminal public pools",
                "kind": kind,
                "network": NETWORKS[chain],
                "pool_id": pool.get("id"),
                "independent_observation": True,
            },
            quality_flags=[] if attrs.get("pool_created_at") else ["missing_launch_time"],
        )
