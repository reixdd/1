from __future__ import annotations

import asyncio
import json
import math
import os
import time
from pathlib import Path
from typing import Any

from .gmgn_bridge import GMGNBridge


def _num(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class OperatorWorkbench:
    """Human-facing composition layer over the proven canonical research runtime.

    No provider polling or research ownership lives here. This service only composes
    existing canonical state into practical operator views and stores UI preferences.
    """

    def __init__(self, runtime) -> None:
        self.runtime = runtime
        self.path = Path(runtime.settings.data_dir) / "operator-state.json"
        self._lock = asyncio.Lock()
        self._state = self._load()
        self.gmgn = GMGNBridge(runtime.metrics, runtime.settings.http_timeout_seconds)

    def _load(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return {
                    "watchlist": list(dict.fromkeys(str(x) for x in raw.get("watchlist", []) if x))[:1000],
                    "chat": list(raw.get("chat", []))[-100:],
                }
        except Exception:
            pass
        return {"watchlist": [], "chat": []}

    async def _save(self) -> None:
        async with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            payload = json.dumps(self._state, ensure_ascii=False, indent=2)
            await asyncio.to_thread(tmp.write_text, payload, encoding="utf-8")
            await asyncio.to_thread(os.replace, tmp, self.path)

    def state(self) -> dict[str, Any]:
        return {
            "watchlist": list(self._state["watchlist"]),
            "chat": list(self._state["chat"][-60:]),
            "research_only": True,
            "transactions_disabled": True,
        }

    async def set_watch(self, identity_key: str, watching: bool) -> dict[str, Any]:
        key = str(identity_key or "").strip()
        if not key or len(key) > 300:
            raise ValueError("invalid identity_key")
        watch = self._state["watchlist"]
        if watching and key not in watch:
            watch.append(key)
        elif not watching and key in watch:
            watch.remove(key)
        self._state["watchlist"] = watch[-1000:]
        await self._save()
        return {"identity_key": key, "watching": key in self._state["watchlist"]}

    async def append_chat(self, role: str, text: str, identity_key: str | None = None) -> None:
        item = {
            "role": role,
            "text": str(text or "")[:12000],
            "identity_key": identity_key,
            "at": time.time(),
        }
        self._state["chat"].append(item)
        self._state["chat"] = self._state["chat"][-100:]
        await self._save()

    def _latest_quant(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for row in self.runtime.quant.recent(1000):
            key = row.get("identity_key")
            if key and key not in out:
                out[key] = row
        return out

    async def radar(self, limit: int = 80) -> dict[str, Any]:
        now = time.time()
        universe = self.runtime.universe.snapshot(limit=2000)
        watched = set(self._state["watchlist"])
        live_items = list(universe.get("items", []))
        live_keys = {row.get("identity_key") for row in live_items}
        # Watched markets stay inspectable after they age out of the young HOT universe.
        # They are clearly marked non-live; this never makes them HOT/Quant eligible again.
        watched_history = [
            state.as_dict(now) | {"live_eligible": False}
            for state in self.runtime.universe.known(10000)
            if state.identity_key in watched and state.identity_key not in live_keys
        ]
        market_items = [dict(row, live_eligible=True) for row in live_items] + watched_history
        qmap = self._latest_quant()
        packets = await self.runtime.evidence.recent_attention(300)
        attention_map: dict[str, Any] = {}
        for packet in packets:
            attention_map.setdefault(packet.identity_key, packet)
        rows = []
        for market in market_items:
            key = market.get("identity_key")
            quant = qmap.get(key, {})
            age = _num(market.get("age_seconds"))
            obs_age = _num(market.get("observation_age_seconds"))
            liq = _num(market.get("liquidity")) or 0.0
            vol = _num(market.get("volume_5m")) or 0.0
            rank = quant.get("rank")
            rank_vel = _num(quant.get("rank_velocity_per_min"))
            providers = int(market.get("provider_count") or 0)
            observations = int(market.get("observation_count") or 0)
            packet = attention_map.get(key)

            score = 0.0
            reasons: list[str] = []
            if age is not None:
                score += 26.0 * (1.0 - _clip(age / max(60.0, self.runtime.settings.young_max_age_seconds), 0.0, 1.0))
                if age <= 180:
                    reasons.append("very new market")
            if rank is not None:
                score += 20.0 / max(1.0, math.sqrt(float(rank)))
            if rank_vel is not None:
                score += _clip(abs(rank_vel) * 1.8, 0.0, 22.0)
                if rank_vel >= 1.0:
                    reasons.append(f"rank improving {rank_vel:+.1f}/min")
                elif rank_vel <= -1.0:
                    reasons.append(f"rank weakening {rank_vel:+.1f}/min")
            turnover = vol / liq if liq > 0 else 0.0
            if turnover > 0:
                score += _clip(math.log1p(turnover) * 12.0, 0.0, 18.0)
                if turnover >= 0.25:
                    reasons.append(f"5m volume/liquidity {turnover:.2f}x")
            if providers >= 2:
                score += min(12.0, providers * 3.0)
                reasons.append(f"{providers} independent market providers")
            if observations >= 3:
                score += min(8.0, math.log1p(observations) * 2.0)
            if packet is not None:
                score += 18.0
                reasons.extend(packet.trigger_reasons[:2])
            if key in watched:
                score += 6.0
            if obs_age is not None and obs_age > self.runtime.settings.observation_fresh_seconds * 0.65:
                score -= 15.0
                reasons.append("observation aging")
            if market.get("live_eligible") is False:
                reasons.insert(0, "watched history; outside the young live universe")
                score = min(score, 5.0)

            if key in watched:
                category = "WATCHED"
            elif packet is not None:
                category = "ATTENTION"
            elif rank_vel is not None and rank_vel >= 1.0:
                category = "SURGING"
            elif age is not None and age <= 180:
                category = "NEW"
            else:
                category = "LIVE"
            rows.append({
                **market,
                "attention_score": round(score, 2),
                "category": category,
                "watching": key in watched,
                "why_surfaced": list(dict.fromkeys(reasons))[:6] or ["young, fresh canonical market observation"],
                "quant": quant,
                "attention": packet.model_dump(mode="json") if packet else None,
            })
        rows.sort(key=lambda r: (r.get("watching", False), r.get("attention_score", 0.0)), reverse=True)
        return {
            "at": now,
            "items": rows[: max(1, min(300, int(limit)))],
            "eligible": universe.get("eligible", 0),
            "known": universe.get("known", 0),
            "watching": len(watched),
            "attention_score_note": "Ranks research attention/novelty only; it is not a buy/sell score or price forecast.",
            "research_only": True,
        }

    def _resolve(self, identity_key: str | None, chain: str | None, contract: str | None):
        if identity_key:
            return self.runtime.universe.get(identity_key)
        if chain and contract:
            return self.runtime.universe.find(chain, contract)
        return None

    async def dossier(self, *, identity_key: str | None = None, chain: str | None = None,
                      contract: str | None = None, include_gmgn: bool = False,
                      include_holders: bool = False) -> dict[str, Any]:
        state = self._resolve(identity_key, chain, contract)
        if state is None:
            return {"found": False, "identity_key": identity_key, "chain": chain, "contract": contract}
        key = state.identity_key
        market = state.as_dict()
        quant_rows = [r for r in self.runtime.quant.recent(1000) if r.get("identity_key") == key][:40]
        observations = await self.runtime.tape.history(key, 240)
        experiments = await self.runtime.ledger.open_experiments(key)
        recent_experiments = [r for r in await self.runtime.ledger.recent_experiments(500) if r.get("identity_key") == key][:50]
        risk, graph, social = await asyncio.gather(
            self.runtime.risk.summary(key),
            self.runtime.graph.neighborhood(key),
            self.runtime.social.summary(key),
        )
        attention = [p.model_dump(mode="json") for p in await self.runtime.evidence.recent_attention(300) if p.identity_key == key][:20]
        memory = await self.runtime.memory.search(state.contract, 60)

        support: list[str] = []
        counter: list[str] = []
        unknowns: list[str] = []
        latest_q = quant_rows[0] if quant_rows else {}
        rank_vel = _num(latest_q.get("rank_velocity_per_min"))
        if rank_vel is not None:
            (support if rank_vel > 0 else counter).append(f"rank velocity {rank_vel:+.1f}/min")
        if state.latest.get("liquidity") is not None:
            support.append("liquidity is currently observable")
        if len(state.providers) >= 2:
            support.append(f"market state cross-observed by {len(state.providers)} providers")
        else:
            unknowns.append("independent market cross-check is limited")
        if risk.get("conflicts"):
            counter.append(f"{len(risk['conflicts'])} security evidence conflict(s)")
        if not risk.get("evidence_count"):
            unknowns.append("security evidence is incomplete")
        if not social.get("independent_mentions"):
            unknowns.append("independent social confirmation is absent")
        if not graph.get("edges"):
            unknowns.append("entity/wallet relationship evidence is thin")

        changed: list[str] = []
        if len(quant_rows) >= 2:
            a, b = quant_rows[0], quant_rows[-1]
            for field, label in (("market_cap", "market cap"), ("liquidity", "liquidity"), ("volume_5m", "5m volume")):
                av, bv = _num(a.get(field)), _num(b.get(field))
                if av is not None and bv not in (None, 0):
                    pct = (av / bv - 1.0) * 100.0
                    if abs(pct) >= 5:
                        changed.append(f"{label} {pct:+.1f}% across recent Quant samples")
            ar, br = a.get("rank"), b.get("rank")
            if ar is not None and br is not None and ar != br:
                changed.append(f"rank {br} → {ar}")

        gmgn = None
        if include_gmgn:
            try:
                gmgn = await self.gmgn.token_bundle(state.chain, state.contract, include_holders=include_holders)
            except Exception as exc:
                gmgn = {"error": f"{type(exc).__name__}: {str(exc)[:300]}", "read_only": True}

        source_links = []
        for obs in observations:
            prov = obs.get("provenance") or {}
            if prov.get("pair_url"):
                source_links.append({"label": "DEX Screener pair", "url": prov["pair_url"], "source": obs.get("provider")})
            if prov.get("profile_url"):
                source_links.append({"label": "DEX profile", "url": prov["profile_url"], "source": obs.get("provider")})
            for link in prov.get("profile_links") or []:
                if isinstance(link, dict) and link.get("url"):
                    source_links.append({"label": link.get("label") or link.get("type") or "profile link", "url": link["url"], "source": obs.get("provider")})
        dedup = {}
        for row in source_links:
            url = str(row.get("url") or "")
            if url.startswith(("https://", "http://")):
                dedup[url] = row

        return {
            "found": True,
            "identity_key": key,
            "market": market,
            "quant": {"latest": latest_q or None, "history": quant_rows},
            "observations": observations,
            "experiments": {"open": [x.model_dump(mode="json") for x in experiments], "recent": recent_experiments},
            "risk": risk,
            "graph": graph,
            "social": social,
            "memory": memory,
            "attention": attention,
            "synthesis": {
                "what_changed": changed or ["No material delta is proven by the recent local samples yet."],
                "support": list(dict.fromkeys(support))[:8],
                "counter_evidence": list(dict.fromkeys(counter))[:8],
                "unknowns": list(dict.fromkeys(unknowns))[:8],
            },
            "source_links": list(dedup.values())[:30],
            "watching": key in self._state["watchlist"],
            "gmgn": gmgn,
            "research_only": True,
            "transactions_disabled": True,
        }

    async def chart(self, identity_key: str, limit: int = 360, gmgn: bool = False) -> dict[str, Any]:
        state = self.runtime.universe.get(identity_key)
        if state is None:
            return {"found": False, "points": []}
        observations = await self.runtime.tape.history(identity_key, limit)
        points = []
        for row in reversed(observations):
            value = _num(row.get("market_cap")) or _num(row.get("price"))
            if value is None:
                continue
            points.append({
                "t": _num(row.get("observed_at")),
                "v": value,
                "market_cap": _num(row.get("market_cap")),
                "price": _num(row.get("price")),
                "liquidity": _num(row.get("liquidity")),
                "volume_5m": _num(row.get("volume_5m")),
                "provider": row.get("provider"),
            })
        gmgn_data = None
        if gmgn:
            try:
                gmgn_data = await self.gmgn.kline(state.chain, state.contract, "1m")
            except Exception as exc:
                gmgn_data = {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
        return {
            "found": True,
            "identity_key": identity_key,
            "basis": "market_cap when present, otherwise price",
            "points": points[-max(20, min(1000, int(limit))):],
            "gmgn_kline": gmgn_data,
        }

    async def overview(self) -> dict[str, Any]:
        radar = await self.radar(20)
        pipeline = self.runtime.pipeline_status(
            self.runtime.metrics.snapshot(), await self.runtime.tape.stats(),
            self.runtime.universe.snapshot(), self.runtime.quant.status(), await self.runtime.ledger.stats()
        )
        return {
            "at": time.time(),
            "pipeline": pipeline,
            "radar": radar,
            "gmgn": await self.gmgn.status(),
            "ollama": self.runtime.ollama.status(),
            "agents": self.runtime.agents.status(),
            "attention": await self.runtime.attention.status(),
            "state": self.state(),
            "research_only": True,
            "transactions_disabled": True,
        }
