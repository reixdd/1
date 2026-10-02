from __future__ import annotations

import math
import time
from typing import Any

try:
    from river import compose, drift, linear_model, metrics as river_metrics, preprocessing
    RIVER_AVAILABLE = True
    RIVER_IMPORT_ERROR = ""
except Exception as exc:  # dependency failure must not stop HOT/Experiments
    compose = drift = linear_model = river_metrics = preprocessing = None
    RIVER_AVAILABLE = False
    RIVER_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

from .leakage import LeakageAuditor
from .metrics import Metrics
from .models import ExperimentRecord, ForwardMark, OnlinePrediction
from .research_ledger import ResearchLedger

LABEL_HORIZON_SECONDS = 900
MODEL_KEY = "river-liquidity-retention-v1"


class OnlineLearner:
    """Strict progressive-validation online learner.

    Prediction happens from frozen T0 features. Learning only happens after a future
    15-minute mark becomes observable. The target is neutral market persistence
    (liquidity retention), not a trade recommendation.
    """

    def __init__(self, ledger: ResearchLedger, metrics: Metrics) -> None:
        self.ledger = ledger
        self.metrics = metrics
        self.available = RIVER_AVAILABLE
        self.import_error = RIVER_IMPORT_ERROR
        self.model = (
            compose.Pipeline(preprocessing.StandardScaler(), linear_model.LogisticRegression())
            if self.available else None
        )
        self.accuracy = river_metrics.Accuracy() if self.available else None
        self.logloss = river_metrics.LogLoss() if self.available else None
        self.drift = drift.ADWIN() if self.available else None
        self.auditor = LeakageAuditor()
        self.drift_events = 0
        self.replayed = 0

    @staticmethod
    def _finite(value: Any, default: float = 0.0) -> float:
        try:
            out = float(value)
            return out if math.isfinite(out) else default
        except (TypeError, ValueError):
            return default

    def freeze_features(self, exp: ExperimentRecord) -> dict[str, float]:
        q = exp.entry_quant
        # Only T0-observable fields are allowed. No forward-return/MFE/MAE fields.
        return {
            "age_seconds": self._finite(q.get("age_seconds")),
            "log_market_cap": math.log1p(max(0.0, self._finite(q.get("market_cap")))),
            "log_liquidity": math.log1p(max(0.0, self._finite(q.get("liquidity")))),
            "log_volume_5m": math.log1p(max(0.0, self._finite(q.get("volume_5m")))),
            "buy_sell_imbalance": self._finite(q.get("buy_sell_imbalance")),
            "rank": self._finite(q.get("rank")),
            "rank_velocity_per_min": self._finite(q.get("rank_velocity_per_min")),
            "provider_count": self._finite(q.get("provider_count")),
            "provider_disagreement": self._finite(q.get("provider_disagreement")),
            "observation_count": self._finite(q.get("observation_count")),
        }

    async def restore(self) -> None:
        if not self.available:
            self.metrics.gauge("online_available", 0)
            return
        self.metrics.gauge("online_available", 1)
        # Rebuild the online model from chronological, already-matured frozen records.
        for prediction in await self.ledger.learned_predictions():
            if prediction.label is None:
                continue
            self._learn_replay(prediction)
            self.replayed += 1
        self.metrics.gauge("online_replayed_predictions", self.replayed)

    async def on_experiment(self, exp: ExperimentRecord) -> OnlinePrediction | None:
        if not self.available:
            self.metrics.inc("online_dependency_missing_total")
            return None
        if await self.ledger.prediction_for_experiment(exp.experiment_id):
            return None
        features = self.freeze_features(exp)
        proba = self.model.predict_proba_one(features)
        predicted = float(proba.get(True, 0.5)) if proba else 0.5
        record = OnlinePrediction(
            experiment_id=exp.experiment_id,
            identity_key=exp.identity_key,
            model_key=MODEL_KEY,
            created_at=exp.opened_at,
            features_frozen_at=exp.opened_at,
            features=features,
            predicted_probability=predicted,
            label_due_at=exp.opened_at + LABEL_HORIZON_SECONDS,
            label_name="liquidity_retention_15m",
        )
        if await self.ledger.insert_prediction(record):
            return record
        return None

    async def on_mark(self, exp: ExperimentRecord, mark: ForwardMark) -> OnlinePrediction | None:
        if not self.available:
            return None
        if mark.horizon_seconds != LABEL_HORIZON_SECONDS:
            return None
        prediction = await self.ledger.prediction_for_experiment(exp.experiment_id)
        if prediction is None or prediction.learned_at is not None:
            return None
        if mark.observed_at < prediction.label_due_at or not mark.complete:
            return None

        entry_liquidity = exp.entry_liquidity
        # The model studies whether the market retained at least 75% of T0 liquidity
        # after 15m. This is a research-quality/persistence target, not a buy/sell label.
        if entry_liquidity is None or entry_liquidity <= 0 or mark.liquidity is None:
            return None
        label = bool(mark.liquidity >= 0.75 * entry_liquidity)
        predicted = prediction.predicted_probability if prediction.predicted_probability is not None else 0.5
        prediction.label = label
        prediction.label_observed_at = mark.observed_at
        prediction.score = 1.0 - abs(float(label) - predicted)
        prediction.leakage_audit = self.auditor.audit_prediction(prediction).code
        if prediction.leakage_audit != "PASS":
            self.metrics.inc("online_leakage_block_total")
            await self.ledger.update_prediction(prediction)
            return prediction

        self.accuracy.update(label, predicted >= 0.5)
        self.logloss.update(label, {False: 1.0 - predicted, True: predicted})
        error = 0.0 if (predicted >= 0.5) == label else 1.0
        self.drift.update(error)
        if self.drift.drift_detected:
            self.drift_events += 1
            self.metrics.inc("online_drift_events_total")
        self.model.learn_one(prediction.features, label)
        prediction.learned_at = time.time()
        await self.ledger.update_prediction(prediction)
        self.metrics.inc("online_labels_total")
        self.metrics.inc("online_model_updates_total")
        return prediction

    def _learn_replay(self, prediction: OnlinePrediction) -> None:
        if not self.available or prediction.label is None:
            return
        predicted = prediction.predicted_probability if prediction.predicted_probability is not None else 0.5
        self.accuracy.update(prediction.label, predicted >= 0.5)
        self.logloss.update(prediction.label, {False: 1.0 - predicted, True: predicted})
        self.model.learn_one(prediction.features, prediction.label)

    def status(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "dependency_error": self.import_error or None,
            "model_key": MODEL_KEY,
            "target": "15m liquidity retention >= 75% of T0 liquidity",
            "protocol": "predict -> freeze -> future label -> score -> learn",
            "accuracy": self.accuracy.get() if self.accuracy is not None else None,
            "log_loss": self.logloss.get() if self.logloss is not None else None,
            "drift_detector": "ADWIN",
            "drift_events": self.drift_events,
            "replayed_predictions": self.replayed,
        }
