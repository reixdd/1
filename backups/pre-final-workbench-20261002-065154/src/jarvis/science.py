from __future__ import annotations

import json
import math
import statistics
import time
from dataclasses import dataclass
from typing import Any

try:
    import polars as pl
    POLARS_AVAILABLE = True
    POLARS_IMPORT_ERROR = ""
except Exception as exc:
    pl = None
    POLARS_AVAILABLE = False
    POLARS_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

try:
    import optuna
    OPTUNA_AVAILABLE = True
except Exception:
    optuna = None
    OPTUNA_AVAILABLE = False

from .history import ColdArchive
from .leakage import LeakageAuditor
from .metrics import Metrics
from .models import OnlinePrediction


@dataclass(frozen=True, slots=True)
class SplitSummary:
    train_n: int
    validation_n: int
    test_n: int
    purge_seconds: int


class ResearchScientist:
    """Chronological COLD research over archived prospective records.

    This component reports descriptive evidence and validation state. It never alters
    live hypotheses or deploys rules automatically.
    """

    def __init__(self, archive: ColdArchive, metrics: Metrics, min_samples: int = 30,
                 purge_seconds: int = 900) -> None:
        self.archive = archive
        self.metrics = metrics
        self.min_samples = max(10, int(min_samples))
        self.purge_seconds = max(0, int(purge_seconds))
        self.auditor = LeakageAuditor()
        self.available = bool(POLARS_AVAILABLE and archive.available)
        self.import_error = POLARS_IMPORT_ERROR or archive.import_error
        self.latest: dict[str, Any] = {
            "state": "WAITING_FOR_PROSPECTIVE_SAMPLES",
            "sample_n": 0,
            "promotion_allowed": False,
        }
        self._stopping = False

    async def run(self) -> None:
        while not self._stopping:
            try:
                await self.run_once()
            except Exception as exc:
                self.metrics.inc("science_errors_total")
                self.latest = {
                    **self.latest,
                    "state": "ERROR",
                    "last_error": f"{type(exc).__name__}: {str(exc)[:300]}",
                }
            try:
                import asyncio
                await asyncio.sleep(600.0)
            except asyncio.CancelledError:
                raise

    def stop(self) -> None:
        self._stopping = True

    async def run_once(self) -> dict[str, Any]:
        if not self.available:
            self.latest = {
                "state": "DEPENDENCIES_MISSING",
                "available": False,
                "dependency_error": self.import_error,
                "sample_n": 0,
                "promotion_allowed": False,
                "updated_at": time.time(),
            }
            return self.latest
        rows = await self.archive.query(
            """SELECT event_time,payload_json FROM research_events
               WHERE record_kind='online_prediction_update'
               ORDER BY event_time ASC"""
        )
        predictions: dict[str, OnlinePrediction] = {}
        leakage_failures: list[dict[str, str]] = []
        for row in rows:
            try:
                prediction = OnlinePrediction.model_validate(json.loads(row["payload_json"]))
            except Exception:
                continue
            if prediction.label is None or prediction.learned_at is None:
                continue
            audit = self.auditor.audit_prediction(prediction)
            if not audit.passed:
                leakage_failures.append({"prediction_id": prediction.prediction_id, "code": audit.code})
                continue
            # Keep the newest update per prediction id.
            predictions[prediction.prediction_id] = prediction

        items = sorted(predictions.values(), key=lambda p: p.created_at)
        if len(items) < self.min_samples:
            self.latest = {
                "state": "WAITING_FOR_PROSPECTIVE_SAMPLES",
                "sample_n": len(items),
                "required_n": self.min_samples,
                "leakage_failures": leakage_failures,
                "promotion_allowed": False,
                "updated_at": time.time(),
            }
            self.metrics.gauge("science_sample_n", len(items))
            return self.latest

        frame = pl.DataFrame([
            {
                "prediction_id": p.prediction_id,
                "created_at": p.created_at,
                "label": int(bool(p.label)),
                "predicted_probability": float(p.predicted_probability or 0.5),
                **{f"f_{k}": float(v) for k, v in p.features.items()},
            }
            for p in items
        ]).sort("created_at")

        train, validation, test = self._chronological_split(frame)
        if min(train.height, validation.height, test.height) == 0:
            self.latest = {
                "state": "INSUFFICIENT_AFTER_PURGE",
                "sample_n": frame.height,
                "promotion_allowed": False,
                "updated_at": time.time(),
            }
            return self.latest

        train_rate = float(train["label"].mean())
        validation_rate = float(validation["label"].mean())
        test_rate = float(test["label"].mean())
        val_brier = self._brier(validation)
        test_brier = self._brier(test)
        bootstrap = self._bootstrap_rate_ci([int(v) for v in validation["label"].to_list()])
        proposal = self._optuna_threshold_proposal(validation)
        test_threshold_score = None
        if proposal is not None:
            test_threshold_score = self._threshold_accuracy(test, float(proposal["threshold"]))

        # Scientist reports evidence only; it cannot deploy or rewrite live rules.
        self.latest = {
            "state": "COMPLETE",
            "sample_n": frame.height,
            "split": {
                "train_n": train.height,
                "validation_n": validation.height,
                "test_n": test.height,
                "purge_seconds": self.purge_seconds,
            },
            "base_rates": {
                "train": train_rate,
                "validation": validation_rate,
                "test_untouched": test_rate,
            },
            "brier": {"validation": val_brier, "test_untouched": test_brier},
            "validation_rate_bootstrap_95": bootstrap,
            "optuna_proposal": proposal,
            "untouched_test_threshold_accuracy": test_threshold_score,
            "leakage_failures": leakage_failures,
            "untouched_test_used_only_for_final_report": True,
            "promotion_allowed": len(leakage_failures) == 0,
            "automatic_deployment": False,
            "updated_at": time.time(),
        }
        self.metrics.inc("science_runs_total")
        self.metrics.gauge("science_sample_n", frame.height)
        self.metrics.gauge("science_leakage_failures", len(leakage_failures))
        return self.latest

    def _chronological_split(self, frame: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
        n = frame.height
        i1 = max(1, int(n * 0.60))
        i2 = max(i1 + 1, int(n * 0.80))
        train_end_time = float(frame.row(i1 - 1, named=True)["created_at"])
        val_start_time = train_end_time + self.purge_seconds
        validation_candidates = frame.filter(pl.col("created_at") > val_start_time)
        if validation_candidates.height < 2:
            return frame.head(i1), frame.head(0), frame.head(0)
        val_count = max(1, int(validation_candidates.height * 0.5))
        validation = validation_candidates.head(val_count)
        val_end_time = float(validation.tail(1).row(0, named=True)["created_at"])
        test_start_time = val_end_time + self.purge_seconds
        test = frame.filter(pl.col("created_at") > test_start_time)
        train = frame.filter(pl.col("created_at") <= train_end_time)
        return train, validation, test


    @staticmethod
    def _threshold_accuracy(frame, threshold: float) -> float:
        probs = [float(v) for v in frame["predicted_probability"].to_list()]
        labels = [bool(v) for v in frame["label"].to_list()]
        if not labels:
            return 0.0
        correct = sum((p >= threshold) == y for p, y in zip(probs, labels))
        return correct / len(labels)

    def _optuna_threshold_proposal(self, validation) -> dict[str, float] | None:
        if not OPTUNA_AVAILABLE or validation.height < 5:
            return None
        sampler = optuna.samplers.TPESampler(seed=1337)
        study = optuna.create_study(direction="maximize", sampler=sampler)

        def objective(trial):
            threshold = trial.suggest_float("threshold", 0.20, 0.80)
            return self._threshold_accuracy(validation, threshold)

        study.optimize(objective, n_trials=25, show_progress_bar=False)
        return {
            "threshold": float(study.best_params["threshold"]),
            "validation_accuracy": float(study.best_value),
            "deployment": "PROPOSAL_ONLY",
        }

    @staticmethod
    def _brier(frame: pl.DataFrame) -> float:
        probs = frame["predicted_probability"].to_list()
        labels = frame["label"].to_list()
        return float(sum((float(p) - float(y)) ** 2 for p, y in zip(probs, labels)) / max(1, len(labels)))

    @staticmethod
    def _bootstrap_rate_ci(labels: list[int], iterations: int = 500) -> list[float] | None:
        if len(labels) < 5:
            return None
        # Deterministic bootstrap for reproducible research reports.
        import random
        rng = random.Random(1337)
        rates = []
        for _ in range(iterations):
            sample = [labels[rng.randrange(len(labels))] for _ in labels]
            rates.append(statistics.fmean(sample))
        rates.sort()
        lo = rates[int(0.025 * (len(rates) - 1))]
        hi = rates[int(0.975 * (len(rates) - 1))]
        return [float(lo), float(hi)]

    def status(self) -> dict[str, Any]:
        return {"available": self.available, "dependency_error": self.import_error or None, **dict(self.latest)}
