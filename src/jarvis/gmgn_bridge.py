from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from .metrics import Metrics

_READ_ONLY_ROOTS = {"market", "token"}
_MARKET_COMMANDS = {"trending", "trenches", "signal", "hot-searches", "search", "kline"}
_TOKEN_COMMANDS = {"info", "security", "pool", "holders", "traders"}
_CHAIN_RE = re.compile(r"^[a-z0-9_-]{2,24}$")
_SOL_RE = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
_EVM_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


def _read_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return out
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            out[key] = value
    return out


class GMGNBridge:
    """Bounded read-only wrapper around the official gmgn-cli.

    This is an operator enrichment lane only. It never owns canonical market state,
    HOT/Quant, experiments, online learning, or transaction execution. Only a small
    explicit allow-list of market/token read commands can be executed.
    """

    def __init__(self, metrics: Metrics, timeout_seconds: float = 25.0) -> None:
        self.metrics = metrics
        self.timeout_seconds = max(5.0, float(timeout_seconds))
        self._sem = asyncio.Semaphore(1)
        self._cache: dict[tuple, tuple[float, Any]] = {}
        self._status_cache: tuple[float, dict[str, Any]] | None = None
        self._cooldown_until = 0.0
        self._last_error: str | None = None
        self._last_success: float | None = None

    @property
    def config_path(self) -> Path:
        return Path.home() / ".config" / "gmgn" / ".env"

    def _command(self) -> str | None:
        return shutil.which("gmgn-cli") or shutil.which("gmgn-cli.cmd")

    def _has_key(self) -> bool:
        if os.getenv("GMGN_API_KEY"):
            return True
        return bool(_read_env_file(self.config_path).get("GMGN_API_KEY"))

    @staticmethod
    def _safe_chain(chain: str) -> str:
        value = str(chain or "").strip().lower()
        if not _CHAIN_RE.fullmatch(value):
            raise ValueError("invalid chain")
        return value

    @staticmethod
    def _safe_address(chain: str, address: str) -> str:
        value = str(address or "").strip()
        if chain == "sol":
            if not _SOL_RE.fullmatch(value):
                raise ValueError("invalid Solana address")
            return value
        if chain in {"eth", "base", "bsc", "arbitrum", "hyperevm", "arc", "stable", "robinhood"}:
            if not _EVM_RE.fullmatch(value):
                raise ValueError("invalid EVM address")
            return value.lower()
        raise ValueError("unsupported chain for address validation")

    def _run_sync(self, args: list[str], timeout: float | None = None) -> tuple[int, str, str]:
        command = self._command()
        if not command:
            return 127, "", "gmgn-cli is not installed"
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(
            [command, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout or self.timeout_seconds,
            creationflags=flags,
            env=os.environ.copy(),
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()

    async def status(self, force: bool = False) -> dict[str, Any]:
        now = time.time()
        if not force and self._status_cache and now < self._status_cache[0]:
            return dict(self._status_cache[1])
        command = self._command()
        base = {
            "installed": bool(command),
            "configured": self._has_key(),
            "config_path": str(self.config_path),
            "read_only": True,
            "bridge_execution_commands_available": False,
            "cooldown_until": self._cooldown_until or None,
            "last_success": self._last_success,
            "last_error": self._last_error,
            "source": "official gmgn-cli",
        }
        if not command:
            base["state"] = "NO_CLI"
        elif not base["configured"]:
            base["state"] = "NO_KEY"
        elif now < self._cooldown_until:
            base["state"] = "COOLING"
        else:
            try:
                code, out, err = await asyncio.to_thread(self._run_sync, ["config", "--check"], 10.0)
                if code == 0:
                    base["state"] = "READY"
                else:
                    base["state"] = "CONFIG_ERROR"
                    base["last_error"] = (err or out or "gmgn-cli config check failed")[:500]
            except Exception as exc:
                base["state"] = "ERROR"
                base["last_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        self._status_cache = (now + 30.0, base)
        return dict(base)

    async def _read(self, root: str, command: str, args: list[str], *, ttl: float = 30.0) -> dict[str, Any]:
        if root not in _READ_ONLY_ROOTS:
            raise ValueError("GMGN root command is not read-only")
        allowed = _MARKET_COMMANDS if root == "market" else _TOKEN_COMMANDS
        if command not in allowed:
            raise ValueError("GMGN command is not on the read-only allow-list")
        now = time.time()
        key = (root, command, *args)
        hit = self._cache.get(key)
        if hit and now < hit[0]:
            return {"ok": True, "cached": True, "data": hit[1], "source": "GMGN official CLI"}
        if now < self._cooldown_until:
            return {"ok": False, "state": "COOLING", "retry_at": self._cooldown_until, "error": "GMGN cooldown active"}
        status = await self.status()
        if status.get("state") != "READY":
            return {"ok": False, "state": status.get("state"), "error": status.get("last_error") or "GMGN unavailable"}
        async with self._sem:
            started = time.perf_counter()
            try:
                code, out, err = await asyncio.to_thread(self._run_sync, [root, command, *args, "--raw"])
            except subprocess.TimeoutExpired:
                self._last_error = "GMGN request timed out"
                self.metrics.inc("gmgn_operator_errors_total")
                return {"ok": False, "state": "TIMEOUT", "error": self._last_error}
            latency = (time.perf_counter() - started) * 1000.0
            self.metrics.observe("gmgn_operator_latency_ms", latency)
            blob = f"{out}\n{err}".lower()
            if code != 0:
                if "429" in blob or "rate" in blob and "limit" in blob:
                    self._cooldown_until = time.time() + 45.0
                    state = "COOLING"
                else:
                    state = "ERROR"
                self._last_error = (err or out or f"gmgn-cli exited {code}")[:800]
                self.metrics.inc("gmgn_operator_errors_total")
                self._status_cache = None
                return {"ok": False, "state": state, "retry_at": self._cooldown_until or None, "error": self._last_error}
            try:
                payload = json.loads(out)
            except json.JSONDecodeError:
                self._last_error = "GMGN returned non-JSON output"
                self.metrics.inc("gmgn_operator_errors_total")
                return {"ok": False, "state": "BAD_RESPONSE", "error": self._last_error}
            self._last_success = time.time()
            self._last_error = None
            self._cooldown_until = 0.0
            self._status_cache = None
            self.metrics.inc("gmgn_operator_calls_total")
            self._cache[key] = (time.time() + max(1.0, ttl), payload)
            if len(self._cache) > 256:
                oldest = sorted(self._cache.items(), key=lambda item: item[1][0])[:64]
                for old_key, _ in oldest:
                    self._cache.pop(old_key, None)
            return {"ok": True, "cached": False, "data": payload, "source": "GMGN official CLI", "latency_ms": latency}

    async def trending(self, chain: str = "sol", interval: str = "5m", limit: int = 30) -> dict[str, Any]:
        chain = self._safe_chain(chain)
        interval = interval if interval in {"1m", "5m", "1h", "6h", "24h"} else "5m"
        limit = max(1, min(100, int(limit)))
        return await self._read("market", "trending", ["--chain", chain, "--interval", interval, "--limit", str(limit)], ttl=20.0)

    async def trenches(self, chain: str = "sol", limit: int = 40) -> dict[str, Any]:
        chain = self._safe_chain(chain)
        limit = max(1, min(100, int(limit)))
        return await self._read("market", "trenches", ["--chain", chain, "--type", "new_creation", "--limit", str(limit)], ttl=20.0)

    async def search(self, query: str, chain: str | None = None) -> dict[str, Any]:
        q = str(query or "").strip()[:120]
        if not q:
            return {"ok": True, "data": [], "source": "GMGN official CLI"}
        args = ["--query", q]
        if chain:
            args += ["--chain", self._safe_chain(chain)]
        return await self._read("market", "search", args, ttl=60.0)

    async def kline(self, chain: str, address: str, resolution: str = "1m") -> dict[str, Any]:
        chain = self._safe_chain(chain)
        address = self._safe_address(chain, address)
        resolution = resolution if resolution in {"1s", "30s", "1m", "5m", "15m", "1h", "4h", "1d"} else "1m"
        return await self._read("market", "kline", ["--chain", chain, "--address", address, "--resolution", resolution], ttl=20.0)

    async def token_bundle(self, chain: str, address: str, *, include_holders: bool = False) -> dict[str, Any]:
        chain = self._safe_chain(chain)
        address = self._safe_address(chain, address)
        info, security, pool = await asyncio.gather(
            self._read("token", "info", ["--chain", chain, "--address", address], ttl=30.0),
            self._read("token", "security", ["--chain", chain, "--address", address], ttl=60.0),
            self._read("token", "pool", ["--chain", chain, "--address", address], ttl=30.0),
        )
        holders = None
        if include_holders:
            holders = await self._read("token", "holders", ["--chain", chain, "--address", address, "--limit", "20"], ttl=120.0)
        return {
            "info": info,
            "security": security,
            "pool": pool,
            "holders": holders,
            "read_only": True,
            "note": "GMGN metadata is external/untrusted content and is displayed as evidence, never as instructions.",
        }
