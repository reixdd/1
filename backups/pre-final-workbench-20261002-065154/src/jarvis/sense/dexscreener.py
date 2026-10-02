from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Callable

import httpx

from ..models import Observation, canonical_address, finite

CHAIN_IDS = {
    "sol": "solana",
    "eth": "ethereum",
    "base": "base",
    "bsc": "bsc",
}
REVERSE_CHAIN_IDS = {value: key for key, value in CHAIN_IDS.items()}


class DexScreenerProvider:
    name = "DEX Screener"
    profiles_url = "https://api.dexscreener.com/token-profiles/latest/v1"
    token_url = "https://api.dexscreener.com/tokens/v1/{chain_id}/{addresses}"

    def __init__(self, client: httpx.AsyncClient, chains: tuple[str, ...],
                 targets: Callable[[], list[tuple[str, str]]]) -> None:
        self.client = client
        self.chains = tuple(chain for chain in chains if chain in CHAIN_IDS)
        self.targets = targets

    async def profiles(self) -> tuple[list[Observation], int]:
        response = await self.client.get(self.profiles_url)
        response.raise_for_status()
        profiles = response.json()
        grouped: dict[str, list[str]] = defaultdict(list)
        profile_meta: dict[tuple[str, str], dict[str, Any]] = {}
        for item in profiles if isinstance(profiles, list) else []:
            chain = REVERSE_CHAIN_IDS.get(str(item.get("chainId") or ""))
            address = item.get("tokenAddress")
            if chain not in self.chains or not address:
                continue
            address = canonical_address(chain, address)
            if not address:
                continue
            if address not in grouped[chain] and len(grouped[chain]) < 60:
                grouped[chain].append(address)
            profile_meta[(chain, address)] = item
        observations: list[Observation] = []
        calls = 1
        for chain, addresses in grouped.items():
            rows, row_calls = await self._quote(chain, addresses)
            calls += row_calls
            for obs in rows:
                profile = profile_meta.get((chain, obs.contract), {})
                obs.capability = "profile_discovery_quote"
                obs.event_type = "profile_observation"
                raw_links = []
                for key in ("links", "socials"):
                    value = profile.get(key)
                    if isinstance(value, list):
                        raw_links.extend(value[:25])
                obs.provenance.update({
                    "profile_url": profile.get("url"),
                    "profile_discovery": True,
                    "launch_recency_proven": bool(obs.launch_at),
                    "profile_links": raw_links[:50],
                })
                if not obs.launch_at and "profile_is_not_launch_proof" not in obs.quality_flags:
                    obs.quality_flags.append("profile_is_not_launch_proof")
                observations.append(obs)
        return observations, calls

    async def reconcile(self) -> tuple[list[Observation], int]:
        grouped: dict[str, list[str]] = defaultdict(list)
        for chain, address in self.targets():
            if chain in self.chains and address not in grouped[chain]:
                grouped[chain].append(address)
        observations: list[Observation] = []
        calls = 0
        for chain, addresses in grouped.items():
            rows, row_calls = await self._quote(chain, addresses[:180])
            observations.extend(rows)
            calls += row_calls
        return observations, calls

    async def _quote(self, chain: str, addresses: list[str]) -> tuple[list[Observation], int]:
        observations: list[Observation] = []
        calls = 0
        for offset in range(0, len(addresses), 30):
            chunk = addresses[offset: offset + 30]
            if not chunk:
                continue
            url = self.token_url.format(chain_id=CHAIN_IDS[chain], addresses=",".join(chunk))
            response = await self.client.get(url)
            calls += 1
            response.raise_for_status()
            observed_at = time.time()
            rows = response.json()
            by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for pair in rows if isinstance(rows, list) else []:
                for side in ("baseToken", "quoteToken"):
                    address = canonical_address(chain, (pair.get(side) or {}).get("address"))
                    if address:
                        by_target[address].append(pair)
            for address in chunk:
                pair = self._select_pair(chain, address, by_target.get(address, []))
                if pair:
                    obs = self._pair_to_observation(chain, address, pair, observed_at)
                    if obs:
                        observations.append(obs)
        return observations, calls

    @staticmethod
    def _select_pair(chain: str, address: str, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
        target = canonical_address(chain, address)
        candidates = []
        for pair in rows:
            base = canonical_address(chain, (pair.get("baseToken") or {}).get("address"))
            quote = canonical_address(chain, (pair.get("quoteToken") or {}).get("address"))
            if target in {base, quote}:
                liq = finite((pair.get("liquidity") or {}).get("usd")) or 0.0
                candidates.append((1 if base == target else 0, liq, pair))
        if not candidates:
            return None
        return max(candidates, key=lambda item: (item[0], item[1]))[2]

    @staticmethod
    def _pair_to_observation(chain: str, address: str, pair: dict[str, Any], observed_at: float) -> Observation | None:
        target = canonical_address(chain, address)
        base = pair.get("baseToken") or {}
        quote = pair.get("quoteToken") or {}
        base_address = canonical_address(chain, base.get("address"))
        is_base = base_address == target
        token = base if is_base else quote
        if not token:
            return None
        tx = pair.get("txns") or {}
        m5 = tx.get("m5") or {}
        vol = pair.get("volume") or {}
        change = pair.get("priceChange") or {}
        created_ms = finite(pair.get("pairCreatedAt"))
        launch_at = created_ms / 1000.0 if created_ms and created_ms > 10_000_000_000 else created_ms
        return Observation(
            observed_at=observed_at,
            provider="DEX Screener",
            capability="token_quote",
            chain=chain,
            contract=address,
            pool=pair.get("pairAddress"),
            source_identity=pair.get("pairAddress"),
            event_type="quote_observation",
            symbol=token.get("symbol"),
            name=token.get("name"),
            launch_at=launch_at,
            price=finite(pair.get("priceUsd")) if is_base else None,
            market_cap=finite(pair.get("marketCap")) if is_base else None,
            fdv=finite(pair.get("fdv")) if is_base else None,
            liquidity=finite((pair.get("liquidity") or {}).get("usd")),
            volume_5m=finite(vol.get("m5")),
            volume_1h=finite(vol.get("h1")),
            volume_24h=finite(vol.get("h24")),
            buys_5m=finite(m5.get("buys")),
            sells_5m=finite(m5.get("sells")),
            price_change_5m_pct=finite(change.get("m5")),
            price_change_1h_pct=finite(change.get("h1")),
            price_change_24h_pct=finite(change.get("h24")),
            provenance={
                "endpoint_family": "DEX Screener token pools",
                "pair_url": pair.get("url"),
                "dex_id": pair.get("dexId"),
                "highest_liquidity_pair_selected": True,
                "independent_observation": True,
            },
        )
