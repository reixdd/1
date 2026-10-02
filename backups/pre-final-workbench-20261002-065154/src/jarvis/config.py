from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True, slots=True)
class Settings:
    host: str
    port: int
    data_dir: Path
    history_dir: Path
    chains: tuple[str, ...]
    young_max_age_seconds: float
    observation_fresh_seconds: float
    tape_retention_hours: float
    gecko_new_interval_seconds: float
    gecko_trending_interval_seconds: float
    dex_profile_interval_seconds: float
    dex_reconcile_interval_seconds: float
    http_timeout_seconds: float
    archive_export_batch_rows: int
    science_min_samples: int
    goplus_enabled: bool = False
    goplus_base_url: str = "https://api.gopluslabs.io"
    goplus_token: str | None = None
    risk_interval_seconds: float = 120.0
    risk_refresh_seconds: float = 900.0
    risk_max_targets_per_cycle: int = 10
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_refresh_seconds: float = 60.0
    agents_enabled: bool = True
    attention_debounce_seconds: float = 2.0
    attention_cooldown_seconds: float = 120.0
    evidence_queue_max: int = 4096

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / "jarvis-operational.sqlite3"

    @classmethod
    def from_env(cls) -> "Settings":
        chains = tuple(
            dict.fromkeys(
                part.strip().lower()
                for part in os.getenv("JARVIS_CHAINS", "sol,base,eth,bsc").replace(";", ",").split(",")
                if part.strip()
            )
        )
        return cls(
            host=os.getenv("JARVIS_HOST", "127.0.0.1"),
            port=_int("JARVIS_PORT", 8768),
            data_dir=Path(os.getenv("JARVIS_DATA_DIR", "./data")).expanduser().resolve(),
            history_dir=Path(os.getenv("JARVIS_HISTORY_DIR", "./history")).expanduser().resolve(),
            chains=chains,
            young_max_age_seconds=max(60.0, _float("JARVIS_YOUNG_MAX_AGE_SECONDS", 900.0)),
            observation_fresh_seconds=max(15.0, _float("JARVIS_OBSERVATION_FRESH_SECONDS", 180.0)),
            tape_retention_hours=max(1.0, _float("JARVIS_TAPE_RETENTION_HOURS", 72.0)),
            gecko_new_interval_seconds=max(15.0, _float("JARVIS_GECKO_NEW_INTERVAL_SECONDS", 45.0)),
            gecko_trending_interval_seconds=max(15.0, _float("JARVIS_GECKO_TRENDING_INTERVAL_SECONDS", 60.0)),
            dex_profile_interval_seconds=max(15.0, _float("JARVIS_DEX_PROFILE_INTERVAL_SECONDS", 60.0)),
            dex_reconcile_interval_seconds=max(5.0, _float("JARVIS_DEX_RECONCILE_INTERVAL_SECONDS", 12.0)),
            http_timeout_seconds=max(3.0, _float("JARVIS_HTTP_TIMEOUT_SECONDS", 15.0)),
            archive_export_batch_rows=max(1000, _int("JARVIS_ARCHIVE_EXPORT_BATCH_ROWS", 10000)),
            science_min_samples=max(10, _int("JARVIS_SCIENCE_MIN_SAMPLES", 30)),
            goplus_enabled=os.getenv("JARVIS_GOPLUS_ENABLED", "0").strip().lower() in {"1","true","yes","on"},
            goplus_base_url=os.getenv("JARVIS_GOPLUS_BASE_URL", "https://api.gopluslabs.io").strip(),
            goplus_token=os.getenv("JARVIS_GOPLUS_TOKEN") or None,
            risk_interval_seconds=max(15.0, _float("JARVIS_RISK_INTERVAL_SECONDS", 120.0)),
            risk_refresh_seconds=max(60.0, _float("JARVIS_RISK_REFRESH_SECONDS", 900.0)),
            risk_max_targets_per_cycle=max(1, min(50, _int("JARVIS_RISK_MAX_TARGETS_PER_CYCLE", 10))),
            ollama_url=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/"),
            ollama_refresh_seconds=max(15.0, _float("JARVIS_OLLAMA_REFRESH_SECONDS", 60.0)),
            agents_enabled=os.getenv("JARVIS_AGENTS_ENABLED", "1").strip().lower() in {"1","true","yes","on"},
            attention_debounce_seconds=max(0.25, _float("JARVIS_ATTENTION_DEBOUNCE_SECONDS", 2.0)),
            attention_cooldown_seconds=max(5.0, _float("JARVIS_ATTENTION_COOLDOWN_SECONDS", 120.0)),
            evidence_queue_max=max(128, min(20000, _int("JARVIS_EVIDENCE_QUEUE_MAX", 4096))),
        )
